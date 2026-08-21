#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compareContinuity, validateProject } from '../../core/continuity.mjs';
import { beginHarnessConnection, confirmHarnessConnection, listHarnesses, runHarness } from '../../core/harness/registry.mjs';
import { applyHarnessResult, buildHarnessPrompt, createWorkspace, workspaceView } from '../../core/workspace.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(HERE, 'public');
const ROOT = path.resolve(HERE, '../..');
const MAX_BODY = 1024 * 1024;
const TYPES = new Map([['.html', 'text/html; charset=utf-8'], ['.css', 'text/css; charset=utf-8'], ['.js', 'text/javascript; charset=utf-8']]);
const WORKSPACES = new Map();

export function createWebServer() {
  return http.createServer(async (request, response) => {
    try { await route(request, response); }
    catch (error) {
      if (error.code === 'BODY_TOO_LARGE') return json(response, 413, { status: 'ERROR', code: error.code, error: error.message });
      if (error.code === 'INVALID_JSON') return json(response, 400, { status: 'ERROR', code: error.code, error: error.message });
      if (error.code?.startsWith('HARNESS_')) return json(response, 422, { status: 'ERROR', code: error.code, error: error.message });
      json(response, 500, { status: 'ERROR', error: 'Unexpected local server error' });
    }
  });
}

async function route(request, response) {
  const url = new URL(request.url, 'http://127.0.0.1');
  if (request.method === 'GET' && url.pathname === '/health') return json(response, 200, { status: 'ok', service: 'sayelf-handdraw-story-web' });
  if (request.method === 'GET' && url.pathname === '/api/harnesses') return json(response, 200, { harnesses: await listHarnesses() });
  const connectMatch = url.pathname.match(/^\/api\/harnesses\/([a-z0-9-]+)\/connect$/);
  if (request.method === 'POST' && connectMatch) return json(response, 200, await beginHarnessConnection(connectMatch[1]));
  const confirmMatch = url.pathname.match(/^\/api\/harnesses\/([a-z0-9-]+)\/confirm$/);
  if (request.method === 'POST' && confirmMatch) {
    const payload = await body(request);
    if (!payload.connectionId) return json(response, 400, { status: 'ERROR', error: 'connectionId is required' });
    const result = await confirmHarnessConnection(payload.connectionId, confirmMatch[1]);
    return json(response, 200, { ...result, harnesses: await listHarnesses() });
  }
  if (request.method === 'POST' && url.pathname === '/api/workspaces') {
    const payload = await body(request);
    const workspace = createWorkspace(payload.language);
    WORKSPACES.set(workspace.id, workspace);
    return json(response, 201, workspaceView(workspace));
  }
  const workspaceMatch = url.pathname.match(/^\/api\/workspaces\/([a-f0-9-]+)$/);
  if (request.method === 'GET' && workspaceMatch) {
    const workspace = WORKSPACES.get(workspaceMatch[1]);
    return workspace ? json(response, 200, workspaceView(workspace)) : json(response, 404, { status: 'ERROR', error: 'Workspace not found' });
  }
  if (request.method === 'POST' && url.pathname === '/api/assist') {
    const payload = await body(request);
    const workspace = WORKSPACES.get(payload.workspaceId);
    if (!workspace) return json(response, 404, { status: 'ERROR', error: 'Workspace not found' });
    const language = payload.language === 'en' ? 'en' : 'zh';
    const prompt = buildHarnessPrompt(workspace, payload.message, language);
    const result = await runHarness(payload.harnessId, { prompt, language, context: { workspaceId: workspace.id } });
    return json(response, 200, applyHarnessResult(workspace, payload.message, result, language));
  }
  if (request.method === 'GET' && url.pathname === '/api/examples') {
    const [previous, current] = await Promise.all([
      readJson(path.join(ROOT, 'examples/story-sequence/shot-01.json')),
      readJson(path.join(ROOT, 'examples/story-sequence/shot-02.json'))
    ]);
    return json(response, 200, { previous, current });
  }
  if (request.method === 'POST' && url.pathname === '/api/validate') {
    const payload = await body(request);
    return json(response, 200, validateProject(payload.project));
  }
  if (request.method === 'POST' && url.pathname === '/api/continuity') {
    const payload = await body(request);
    return json(response, 200, compareContinuity(payload.previous, payload.current));
  }
  if (request.method === 'GET' || request.method === 'HEAD') {
    const relative = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
    const resolved = path.resolve(PUBLIC, relative);
    if (resolved !== PUBLIC && !resolved.startsWith(`${PUBLIC}${path.sep}`)) return text(response, 403, 'Forbidden');
    try {
      const content = await fs.readFile(resolved);
      response.writeHead(200, { 'content-type': TYPES.get(path.extname(resolved)) || 'application/octet-stream', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
      return response.end(request.method === 'HEAD' ? undefined : content);
    } catch (error) {
      if (error.code === 'ENOENT') return text(response, 404, 'Not found');
      throw error;
    }
  }
  text(response, 405, 'Method not allowed');
}

async function body(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY) { const error = new Error('Request body exceeds 1 MB'); error.code = 'BODY_TOO_LARGE'; throw error; }
    chunks.push(chunk);
  }
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}'); }
  catch { const error = new Error('Request body must be valid JSON'); error.code = 'INVALID_JSON'; throw error; }
}

async function readJson(file) { return JSON.parse(await fs.readFile(file, 'utf8')); }
function json(response, status, payload) {
  const content = JSON.stringify(payload);
  response.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'content-length': Buffer.byteLength(content), 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
  response.end(content);
}
function text(response, status, content) { response.writeHead(status, { 'content-type': 'text/plain; charset=utf-8' }); response.end(content); }

export function startWebServer({ host = '127.0.0.1', port = 4175 } = {}) {
  const server = createWebServer();
  server.listen(port, host, () => console.log(`Sayelf Handdraw Story WebUI: http://${host}:${server.address().port}`));
  return server;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) startWebServer({ port: Number(process.env.PORT || 4175) });
