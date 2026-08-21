#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compareContinuity, validateProject } from '../../core/continuity.mjs';

const [, , command, inputPath, ...rest] = process.argv;
if (!command || !inputPath) usage(1);

try {
  const current = readJson(inputPath);
  let result;
  if (command === 'validate') {
    result = validateProject(current);
  } else if (command === 'continuity') {
    const flags = parseFlags(rest);
    if (!flags.previous) throw new Error('--previous <file> is required for continuity');
    result = compareContinuity(readJson(flags.previous), current);
  } else {
    usage(1);
  }
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = result.status === 'PASS' ? 0 : 2;
} catch (error) {
  console.error(JSON.stringify({ status: 'ERROR', error: error.message }, null, 2));
  process.exitCode = 1;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(path.resolve(process.cwd(), file), 'utf8'));
}

function parseFlags(args) {
  const flags = {};
  for (let index = 0; index < args.length; index += 1) {
    if (!args[index].startsWith('--')) continue;
    const key = args[index].slice(2);
    const value = args[index + 1];
    if (!value || value.startsWith('--')) flags[key] = true;
    else {
      flags[key] = value;
      index += 1;
    }
  }
  return flags;
}

function usage(code) {
  const script = path.basename(fileURLToPath(import.meta.url));
  console.log(`Usage:\n  node ${script} validate <project.json>\n  node ${script} continuity <project.json> --previous <project.json>`);
  process.exit(code);
}
