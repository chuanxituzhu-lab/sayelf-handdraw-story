import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createWorkspace } from '../core/workspace.mjs';
import { tryLocalAssist } from '../core/local-assist.mjs';

const project = JSON.parse(fs.readFileSync(new URL('../examples/story-sequence/shot-01.json', import.meta.url), 'utf8'));

test('local assist handles deterministic checks without a model call', () => {
  const workspace = createWorkspace('zh'); workspace.project = project;
  const result = tryLocalAssist(workspace, '检查连续性', 'zh');
  assert.match(result.text, /本地连续性检查/);
  assert.equal(result.data, null);
});

test('local assist declines creative requests for the harness', () => {
  const workspace = createWorkspace('en'); workspace.project = project;
  assert.equal(tryLocalAssist(workspace, '把第二个镜头改成黄昏', 'en'), null);
});

test('local assist plans the fox opening offline', () => {
  const workspace = createWorkspace('zh');
  const result = tryLocalAssist(workspace, '一只戴红围巾的小狐狸，在雪地里寻找回家的路。请规划前两个镜头', 'zh');
  assert.match(result.text, /镜头 1/);
  assert.match(result.text, /镜头 2/);
});
