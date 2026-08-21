import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { once } from 'node:events';
import { createWebServer } from '../interfaces/web/server.mjs';

const read = (name) => JSON.parse(fs.readFileSync(new URL(`../examples/story-sequence/${name}`, import.meta.url), 'utf8'));
async function fixture(run) {
  const server = createWebServer(); server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try { await run(`http://127.0.0.1:${server.address().port}`); }
  finally { server.close(); await once(server, 'close'); }
}

test('WebUI and health endpoint are served locally', () => fixture(async (base) => {
  const health = await fetch(`${base}/health`);
  assert.equal(health.status, 200);
  assert.deepEqual(await health.json(), { status: 'ok', service: 'sayelf-handdraw-story-web' });
  const page = await fetch(base);
  assert.equal(page.status, 200);
  assert.match(page.headers.get('content-type'), /text\/html/);
  assert.match(await page.text(), /图片故事连续性/);
}));

test('validate API returns PASS for the bundled project', () => fixture(async (base) => {
  const response = await fetch(`${base}/api/validate`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ project: read('shot-01.json') }) });
  assert.deepEqual(await response.json(), { status: 'PASS', issues: [] });
}));

test('continuity API reports character drift', () => fixture(async (base) => {
  const previous = read('shot-01.json'); const current = read('shot-02.json');
  current.characters[0].visual_identity.costume = 'green coat';
  const response = await fetch(`${base}/api/continuity`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ previous, current }) });
  const report = await response.json();
  assert.equal(report.status, 'REVISE');
  assert.ok(report.drifts.some((item) => item.code === 'CHARACTER_IDENTITY'));
}));

test('oversized bodies are rejected', () => fixture(async (base) => {
  const response = await fetch(`${base}/api/validate`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ project: { padding: 'x'.repeat(1024 * 1024) } }) });
  assert.equal(response.status, 413);
}));

test('WebUI creates a hidden workspace and talks to an enabled harness', () => fixture(async (base) => {
  const created = await fetch(`${base}/api/workspaces`, { method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({ language:'en' }) });
  const workspace = await created.json();
  assert.equal(created.status, 201);
  assert.equal('project' in workspace, false);
  const harnesses = await (await fetch(`${base}/api/harnesses`)).json();
  assert.equal(harnesses.harnesses.find((item) => item.id === 'local-guide').enabled, true);
  const response = await fetch(`${base}/api/assist`, { method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({ workspaceId:workspace.id, harnessId:'local-guide', message:'help', language:'en' }) });
  const result = await response.json();
  assert.equal(response.status, 200);
  assert.match(result.reply, /local guide/i);
  assert.equal('project' in result.workspace, false);
}));

test('external harnesses require human authorization confirmation before connection', () => fixture(async (base) => {
  const started = await fetch(`${base}/api/harnesses/codex/connect`, { method: 'POST' });
  assert.equal(started.status, 200);
  const pending = await started.json();
  assert.match(pending.authUrl, /^https:\/\//);
  const before = await (await fetch(`${base}/api/harnesses`)).json();
  assert.equal(before.harnesses.find((item) => item.id === 'codex').connected, false);
  const confirmed = await fetch(`${base}/api/harnesses/codex/confirm`, { method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({ connectionId: pending.connectionId }) });
  assert.equal(confirmed.status, 200);
  const result = await confirmed.json();
  assert.equal(result.connected, true);
  assert.equal(result.harnesses.find((item) => item.id === 'codex').enabled, true);
}));
