import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { listHarnesses, runHarness } from '../core/harness/registry.mjs';

test('builtin guide is enabled while external harnesses require an allowlist', async () => {
  const harnesses = await listHarnesses({ allow: '' });
  assert.equal(harnesses.find((item) => item.id === 'local-guide').enabled, true);
  assert.equal(harnesses.find((item) => item.id === 'codex').enabled, false);
  assert.ok(harnesses.some((item) => item.transport === 'mcp-http'));
});

test('disabled harness cannot execute', async () => {
  await assert.rejects(() => runHarness('codex', { prompt: 'hello' }, { allow: '' }), (error) => error.code === 'HARNESS_DISABLED');
});

test('CLI plugins execute without a shell and normalize JSON output', async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'sayelf-plugin-'));
  const fixture = path.resolve('tests/fixtures/fake-harness.mjs');
  await fs.writeFile(path.join(directory, 'fixture.json'), JSON.stringify({ id:'fixture-cli', transport:'cli', command:process.execPath, args:[fixture,'{{prompt}}'], output:'json', name:{zh:'测试',en:'Fixture'} }));
  try {
    const result = await runHarness('fixture-cli', { prompt: 'safe prompt' }, { pluginDir: directory, allow: 'fixture-cli' });
    assert.match(result.text, /fixture:safe prompt/);
  } finally { await fs.rm(directory, { recursive: true, force: true }); }
});

test('unknown transports and malformed manifests fail closed', async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'sayelf-plugin-'));
  await fs.writeFile(path.join(directory, 'bad.json'), JSON.stringify({ id:'bad-plugin', transport:'shell', name:{zh:'坏',en:'Bad'} }));
  try { await assert.rejects(() => listHarnesses({ pluginDir: directory }), /invalid transport/); }
  finally { await fs.rm(directory, { recursive: true, force: true }); }
});
