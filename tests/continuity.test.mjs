import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { compareContinuity, validateProject } from '../core/continuity.mjs';

const read = (name) => JSON.parse(fs.readFileSync(new URL(`../examples/story-sequence/${name}`, import.meta.url), 'utf8'));

test('valid hand-drawn story project passes structural and reference checks', () => {
  assert.deepEqual(validateProject(read('shot-01.json')), { status: 'PASS', issues: [] });
});

test('a later shot may change composition while stable identities remain continuous', () => {
  const report = compareContinuity(read('shot-01.json'), read('shot-02.json'));
  assert.equal(report.status, 'PASS');
  assert.deepEqual(report.drifts, []);
});

test('character costume drift is reported with a stable path', () => {
  const previous = read('shot-01.json');
  const current = read('shot-02.json');
  current.characters[0].visual_identity.costume = 'red sweater';
  const report = compareContinuity(previous, current);
  assert.equal(report.status, 'REVISE');
  assert.ok(report.drifts.some((drift) => drift.code === 'CHARACTER_IDENTITY' && drift.path.includes('child')));
});

test('style comparison ignores JSON object key order but catches actual changes', () => {
  const previous = read('shot-01.json');
  const current = read('shot-02.json');
  assert.equal(compareContinuity(previous, current).status, 'PASS');
  current.style.color.palette = 'neon';
  assert.ok(compareContinuity(previous, current).drifts.some((drift) => drift.code === 'STYLE'));
});

test('broken references and out-of-range timeline values fail validation', () => {
  const project = read('shot-01.json');
  project.scenes[0].characters.push('missing-character');
  project.frames[0].time = 9;
  project.motions[0].duration = 9;
  const report = validateProject(project);
  assert.equal(report.status, 'REVISE');
  assert.ok(report.issues.some((item) => item.code === 'BROKEN_REFERENCE'));
  assert.ok(report.issues.some((item) => item.code === 'FRAME_TIME'));
  assert.ok(report.issues.some((item) => item.code === 'MOTION_TIME'));
});

test('duplicate identifiers are rejected deterministically', () => {
  const project = read('shot-01.json');
  project.characters.push(structuredClone(project.characters[0]));
  const report = validateProject(project);
  assert.equal(report.status, 'REVISE');
  assert.ok(report.issues.some((item) => item.code === 'DUPLICATE_ID'));
});
