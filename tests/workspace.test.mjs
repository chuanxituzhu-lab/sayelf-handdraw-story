import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { applyHarnessResult, buildHarnessPrompt, createWorkspace, workspaceView } from '../core/workspace.mjs';

const project = JSON.parse(fs.readFileSync(new URL('../examples/story-sequence/shot-01.json', import.meta.url), 'utf8'));

test('workspace view never exposes hidden project JSON', () => {
  const workspace = createWorkspace('zh');
  workspace.project = project;
  const view = workspaceView(workspace);
  assert.equal('project' in view, false);
  assert.equal(view.summary.title, 'The Paper Boat');
});

test('only a valid harness project is accepted into backstage state', () => {
  const workspace = createWorkspace('en');
  const accepted = applyHarnessResult(workspace, 'plan', { text:'done', data:{ message:'done', project } }, 'en');
  assert.equal(accepted.projectAccepted, true);
  assert.equal(accepted.workspace.hasProject, true);
  const invalid = structuredClone(project); invalid.frames[0].time = 99;
  const rejected = applyHarnessResult(workspace, 'change', { text:'changed', data:{ message:'changed', project:invalid } }, 'en');
  assert.equal(rejected.projectAccepted, false);
  assert.equal(rejected.validation.status, 'REVISE');
});

test('harness prompt includes a language contract and hidden context', () => {
  const workspace = createWorkspace('zh'); workspace.project = project;
  const prompt = buildHarnessPrompt(workspace, '继续故事', 'zh');
  assert.match(prompt, /不要展示原始项目 JSON/);
  assert.match(prompt, /The Paper Boat/);
});
