import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const BUILTIN_DIR = path.join(ROOT, 'plugins/harness');
const MAX_OUTPUT = 2 * 1024 * 1024;

export async function listHarnesses(options = {}) {
  const plugins = await loadPlugins(options);
  return plugins.map((plugin) => publicPlugin(plugin, options));
}

export async function runHarness(id, request, options = {}) {
  const plugin = (await loadPlugins(options)).find((item) => item.id === id);
  if (!plugin) throw coded('HARNESS_NOT_FOUND', `Unknown harness: ${id}`);
  if (!enabled(plugin, options)) throw coded('HARNESS_DISABLED', `Harness is not enabled: ${id}`);
  const prompt = String(request.prompt || '').trim();
  if (!prompt) throw coded('PROMPT_REQUIRED', 'Prompt is required');

  if (plugin.transport === 'builtin') return builtinGuide(prompt, request.language);
  if (plugin.transport === 'cli') return runCli(plugin, prompt, options);
  if (plugin.transport === 'http') return runHttp(plugin, request, options);
  if (plugin.transport === 'mcp-http') return runMcpHttp(plugin, request, options);
  throw coded('HARNESS_TRANSPORT', `Unsupported harness transport: ${plugin.transport}`);
}

async function loadPlugins(options) {
  const directories = [BUILTIN_DIR];
  const external = options.pluginDir || process.env.SAYELF_PLUGIN_DIR;
  if (external) directories.push(path.resolve(external));
  const byId = new Map();
  for (const directory of directories) {
    let entries = [];
    try { entries = await fs.readdir(directory, { withFileTypes: true }); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    for (const entry of entries.filter((item) => item.isFile() && item.name.endsWith('.json')).sort((a, b) => a.name.localeCompare(b.name))) {
      const plugin = JSON.parse(await fs.readFile(path.join(directory, entry.name), 'utf8'));
      validateManifest(plugin, entry.name);
      byId.set(plugin.id, Object.freeze(plugin));
    }
  }
  return [...byId.values()].sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
}

function validateManifest(plugin, source) {
  if (!plugin || typeof plugin !== 'object') throw new Error(`${source}: plugin must be an object`);
  if (!/^[a-z0-9][a-z0-9-]{1,62}$/.test(plugin.id || '')) throw new Error(`${source}: invalid plugin id`);
  if (!['builtin', 'cli', 'http', 'mcp-http'].includes(plugin.transport)) throw new Error(`${source}: invalid transport`);
  if (!plugin.name || typeof plugin.name !== 'object') throw new Error(`${source}: localized name is required`);
  if (plugin.transport === 'cli' && (typeof plugin.command !== 'string' || !Array.isArray(plugin.args))) throw new Error(`${source}: CLI command and args are required`);
  if (['http', 'mcp-http'].includes(plugin.transport) && typeof plugin.endpoint !== 'string') throw new Error(`${source}: endpoint is required`);
  plugin.order = Number(plugin.order || 100);
}

function enabled(plugin, options) {
  if (plugin.transport === 'builtin') return true;
  const allow = String(options.allow || process.env.SAYELF_HARNESS_ALLOW || '').split(',').map((item) => item.trim()).filter(Boolean);
  return allow.includes(plugin.id) || allow.includes('*');
}

function publicPlugin(plugin, options) {
  return {
    id: plugin.id,
    name: plugin.name,
    description: plugin.description,
    transport: plugin.transport,
    enabled: enabled(plugin, options),
    capabilities: plugin.capabilities || ['assist']
  };
}

async function runCli(plugin, prompt, options) {
  const args = plugin.args.map((value) => value === '{{prompt}}' ? prompt : value);
  const useStdin = !plugin.args.includes('{{prompt}}');
  const timeoutMs = clamp(plugin.timeoutMs, 1000, options.maxTimeoutMs || 120000, 60000);
  const cwd = path.resolve(options.cwd || ROOT);
  return new Promise((resolve, reject) => {
    const child = spawn(plugin.command, args, { cwd, shell: false, windowsHide: true, env: process.env, stdio: ['pipe', 'pipe', 'pipe'] });
    const stdout = []; const stderr = []; let bytes = 0; let settled = false;
    const timer = setTimeout(() => { child.kill(); finish(reject, coded('HARNESS_TIMEOUT', `${plugin.id} exceeded ${timeoutMs} ms`)); }, timeoutMs);
    const collect = (target) => (chunk) => { bytes += chunk.length; if (bytes > MAX_OUTPUT) { child.kill(); finish(reject, coded('HARNESS_OUTPUT_LIMIT', 'Harness output exceeds 2 MB')); } else target.push(chunk); };
    child.stdout.on('data', collect(stdout)); child.stderr.on('data', collect(stderr));
    child.on('error', (error) => finish(reject, coded('HARNESS_START_FAILED', error.message)));
    child.on('close', (code) => {
      if (code !== 0) return finish(reject, coded('HARNESS_FAILED', Buffer.concat(stderr).toString('utf8').trim() || `Harness exited with code ${code}`));
      finish(resolve, normalizeOutput(Buffer.concat(stdout).toString('utf8'), plugin.output));
    });
    if (useStdin) child.stdin.end(prompt); else child.stdin.end();
    function finish(callback, value) { if (settled) return; settled = true; clearTimeout(timer); callback(value); }
  });
}

async function runHttp(plugin, request, options) {
  const endpoint = endpointFor(plugin, options);
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), clamp(plugin.timeoutMs, 1000, 120000, 60000));
  try {
    const response = await fetch(endpoint, { method: 'POST', headers: requestHeaders(plugin), body: JSON.stringify({ prompt: request.prompt, language: request.language, context: request.context }), signal: controller.signal });
    const body = await response.text();
    if (!response.ok) throw coded('HARNESS_HTTP', `HTTP ${response.status}: ${body.slice(0, 500)}`);
    return normalizeOutput(body, plugin.output || 'json');
  } catch (error) {
    if (error.name === 'AbortError') throw coded('HARNESS_TIMEOUT', `${plugin.id} request timed out`);
    throw error;
  } finally { clearTimeout(timer); }
}

async function runMcpHttp(plugin, request, options) {
  const endpoint = endpointFor(plugin, options);
  const signal = AbortSignal.timeout(clamp(plugin.timeoutMs, 1000, 120000, 60000));
  let sequence = 1; let sessionId;
  const rpc = async (method, params, notification = false) => {
    const payload = { jsonrpc: '2.0', method, ...(params ? { params } : {}), ...(notification ? {} : { id: sequence++ }) };
    const headers = requestHeaders(plugin); if (sessionId) headers['mcp-session-id'] = sessionId;
    let response;
    try { response = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(payload), signal }); }
    catch (error) {
      if (error.name === 'TimeoutError' || error.name === 'AbortError') throw coded('HARNESS_TIMEOUT', `${plugin.id} request timed out`);
      throw error;
    }
    sessionId ||= response.headers.get('mcp-session-id') || undefined;
    if (!response.ok) throw coded('HARNESS_MCP', `MCP HTTP ${response.status}`);
    if (notification || response.status === 202) return null;
    const result = await response.json(); if (result.error) throw coded('HARNESS_MCP', result.error.message || 'MCP error'); return result.result;
  };
  await rpc('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'sayelf-handdraw-story', version: '0.1.0' } });
  await rpc('notifications/initialized', null, true);
  if (plugin.initTool) await rpc('tools/call', { name: plugin.initTool, arguments: interpolate(plugin.initArguments || {}) });
  const tool = plugin.tool;
  const args = structuredClone(plugin.arguments || {});
  setPath(args, plugin.promptField || 'prompt', request.prompt);
  const result = await rpc('tools/call', { name: tool, arguments: args });
  const text = (result?.content || []).filter((item) => item.type === 'text').map((item) => item.text).join('\n');
  return normalizeOutput(text || JSON.stringify(result?.structuredContent || {}), plugin.output || 'text');
}

function requestHeaders(plugin) {
  const headers = { 'content-type': 'application/json', accept: 'application/json, text/event-stream' };
  if (plugin.authEnv && process.env[plugin.authEnv]) headers.authorization = `Bearer ${process.env[plugin.authEnv]}`;
  return headers;
}
function endpointFor(plugin, options) {
  const override = options.endpoints?.[plugin.id] || process.env[`SAYELF_${plugin.id.toUpperCase().replaceAll('-', '_')}_ENDPOINT`];
  const endpoint = override || plugin.endpoint;
  const url = new URL(endpoint);
  if (!['http:', 'https:'].includes(url.protocol)) throw coded('HARNESS_ENDPOINT', 'Only HTTP(S) endpoints are allowed');
  return url;
}
function normalizeOutput(raw, format = 'text') {
  const text = String(raw || '').trim();
  if (format === 'json') {
    try {
      const wrapper = JSON.parse(text);
      const content = wrapper.message || wrapper.result || wrapper.response || text;
      const embedded = typeof content === 'string' ? extractJson(content) : null;
      return { text: typeof content === 'string' ? content : text, data: wrapper.project ? wrapper : embedded || wrapper };
    }
    catch { return { text, data: null }; }
  }
  return { text, data: extractJson(text) };
}
function extractJson(text) {
  const match = text.match(/```json\s*([\s\S]*?)```/i);
  const candidate = match?.[1] || (text.trim().startsWith('{') ? text : null);
  if (!candidate) return null;
  try { return JSON.parse(candidate); } catch { return null; }
}
function setPath(target, dottedPath, value) {
  const parts = dottedPath.split('.'); let cursor = target;
  for (const part of parts.slice(0, -1)) cursor = cursor[part] ||= {};
  cursor[parts.at(-1)] = value;
}
function interpolate(value) {
  if (Array.isArray(value)) return value.map(interpolate);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, interpolate(item)]));
  if (typeof value === 'string') {
    const match = value.match(/^\{\{env:([A-Z0-9_]+)}}$/);
    if (match) {
      if (!process.env[match[1]]) throw coded('HARNESS_ENV', `Missing environment variable: ${match[1]}`);
      return process.env[match[1]];
    }
  }
  return value;
}
function builtinGuide(_prompt, language) {
  return language === 'en'
    ? { text: 'The local guide is ready. Enable Codex, Claude Code, WorkBuddy, or another plugin on the server to request AI planning.', data: null }
    : { text: '本地引导已就绪。请在服务端启用 Codex、Claude Code、WorkBuddy 或其他插件后发起 AI 规划。', data: null };
}
function coded(code, message) { const error = new Error(message); error.code = code; return error; }
function clamp(value, min, max, fallback) { const number = Number(value); return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : fallback; }
