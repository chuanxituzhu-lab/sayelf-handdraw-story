const VERSION = '0.1.0';

/** Validate the project invariants that JSON Schema alone cannot express. */
export function validateProject(project) {
  const issues = [];
  const warn = (code, path, message) => issues.push({ severity: 'error', code, path, message });

  if (!isObject(project)) {
    warn('PROJECT_TYPE', '$', 'project must be an object');
    return report(issues);
  }
  if (project.version !== VERSION) warn('VERSION', '$.version', `version must be ${VERSION}`);
  if (!isObject(project.story) || !text(project.story.title)) warn('STORY', '$.story', 'story.title is required');
  if (!isObject(project.style) || !text(project.style.id)) warn('STYLE', '$.style', 'style.id is required');

  const characters = index(project.characters, '$.characters', issues);
  const props = index(project.props, '$.props', issues);
  const scenes = index(project.scenes, '$.scenes', issues);
  const shots = index(project.shots, '$.shots', issues);
  const frames = index(project.frames, '$.frames', issues);
  const motions = index(project.motions, '$.motions', issues);
  const beats = new Set((project.story?.beats || []).map((item) => item?.id).filter(Boolean));

  for (const [id, scene] of scenes) {
    references(scene.beat_ids, beats, `$.scenes[id=${id}].beat_ids`, 'beat', issues);
    references(scene.characters, new Set(characters.keys()), `$.scenes[id=${id}].characters`, 'character', issues);
    references(scene.props, new Set(props.keys()), `$.scenes[id=${id}].props`, 'prop', issues);
    references(scene.shot_ids, new Set(shots.keys()), `$.scenes[id=${id}].shot_ids`, 'shot', issues);
  }
  for (const [id, shot] of shots) {
    reference(shot.scene_id, scenes, `$.shots[id=${id}].scene_id`, 'scene', issues);
    references(shot.subject_ids, union(characters, props), `$.shots[id=${id}].subject_ids`, 'subject', issues);
    references(shot.frame_ids, new Set(frames.keys()), `$.shots[id=${id}].frame_ids`, 'frame', issues);
    references(shot.motion_ids, new Set(motions.keys()), `$.shots[id=${id}].motion_ids`, 'motion', issues);
    if (!(Number.isFinite(shot.duration) && shot.duration > 0)) {
      issues.push(issue('SHOT_DURATION', `$.shots[id=${id}].duration`, 'shot duration must be greater than zero'));
    }
  }
  for (const [id, frame] of frames) {
    const shot = shots.get(frame.shot_id);
    reference(frame.shot_id, shots, `$.frames[id=${id}].shot_id`, 'shot', issues);
    if (shot && (!Number.isFinite(frame.time) || frame.time < 0 || frame.time > shot.duration)) {
      issues.push(issue('FRAME_TIME', `$.frames[id=${id}].time`, 'frame time must fall within its shot duration'));
    }
  }
  for (const [id, motion] of motions) {
    const shot = shots.get(motion.shot_id);
    reference(motion.shot_id, shots, `$.motions[id=${id}].shot_id`, 'shot', issues);
    if (shot && (!Number.isFinite(motion.start) || !Number.isFinite(motion.duration) || motion.start < 0 || motion.duration <= 0 || motion.start + motion.duration > shot.duration)) {
      issues.push(issue('MOTION_TIME', `$.motions[id=${id}]`, 'motion must fit within its shot duration'));
    }
  }

  return report(issues);
}

/** Compare stable story-level visual identities across two project snapshots. */
export function compareContinuity(previous, current) {
  const validation = validateProject(current);
  if (!isObject(previous)) return { status: validation.status, drifts: [], validation };

  const drifts = [];
  compareStable('style', previous.style, current.style, '$.style', drifts);
  compareMembers('character', previous.characters, current.characters, 'visual_identity', drifts);
  compareMembers('prop', previous.props, current.props, 'visual_identity', drifts);

  const previousScenes = index(previous.scenes);
  const currentScenes = index(current.scenes);
  for (const [id, before] of previousScenes) {
    const after = currentScenes.get(id);
    if (!after) continue;
    compareStable('scene-location', before.location, after.location, `$.scenes[id=${id}].location`, drifts);
    compareStable('scene-time', before.time_of_day, after.time_of_day, `$.scenes[id=${id}].time_of_day`, drifts);
  }

  drifts.sort((a, b) => a.path.localeCompare(b.path) || a.code.localeCompare(b.code));
  return {
    status: validation.status === 'PASS' && drifts.length === 0 ? 'PASS' : 'REVISE',
    drifts,
    validation
  };
}

function compareMembers(kind, beforeList = [], afterList = [], field, drifts) {
  const after = index(afterList);
  for (const [id, beforeItem] of index(beforeList)) {
    const afterItem = after.get(id);
    if (!afterItem) continue;
    compareStable(`${kind}-identity`, beforeItem[field], afterItem[field], `$.${kind === 'character' ? 'characters' : 'props'}[id=${id}].${field}`, drifts);
  }
}

function compareStable(code, before, after, path, drifts) {
  if (before === undefined || after === undefined || same(before, after)) return;
  drifts.push({ code: code.toUpperCase().replaceAll('-', '_'), path, previous: before, current: after });
}

function index(items, path = '$', issues = []) {
  const result = new Map();
  if (items === undefined) return result;
  if (!Array.isArray(items)) {
    issues.push(issue('COLLECTION_TYPE', path, 'value must be an array'));
    return result;
  }
  items.forEach((item, position) => {
    if (!isObject(item) || !text(item.id)) {
      issues.push(issue('ITEM_ID', `${path}[${position}]`, 'item must have a non-empty id'));
    } else if (result.has(item.id)) {
      issues.push(issue('DUPLICATE_ID', `${path}[${position}].id`, `duplicate id: ${item.id}`));
    } else {
      result.set(item.id, item);
    }
  });
  return result;
}

function reference(value, targets, path, kind, issues) {
  if (!text(value) || !targets.has(value)) issues.push(issue('BROKEN_REFERENCE', path, `unknown ${kind}: ${String(value)}`));
}

function references(values, targets, path, kind, issues) {
  if (values === undefined) return;
  if (!Array.isArray(values)) return issues.push(issue('REFERENCE_TYPE', path, 'references must be an array'));
  values.forEach((value, position) => reference(value, targets, `${path}[${position}]`, kind, issues));
}

function union(...maps) {
  return new Set(maps.flatMap((map) => [...map.keys()]));
}

function report(issues) {
  issues.sort((a, b) => a.path.localeCompare(b.path) || a.code.localeCompare(b.code));
  return { status: issues.length ? 'REVISE' : 'PASS', issues };
}

function issue(code, path, message) {
  return { severity: 'error', code, path, message };
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function text(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function same(left, right) {
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (!isObject(value)) return value;
  return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
}
