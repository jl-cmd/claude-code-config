import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const convergeSource = readFileSync(join(workflowDirectory, 'converge.mjs'), 'utf8');
const gotchasSource = readFileSync(
  join(workflowDirectory, '..', 'reference', 'gotchas.md'),
  'utf8',
);

function lensPromptBody(builderName) {
  const builderStart = convergeSource.indexOf(`function ${builderName}(`);
  assert.notEqual(builderStart, -1, `expected ${builderName} to exist`);
  const nextBuilderStart = convergeSource.indexOf('\nfunction ', builderStart + 1);
  const builderEnd = nextBuilderStart === -1 ? convergeSource.length : nextBuilderStart;
  return convergeSource.slice(builderStart, builderEnd);
}

test('code-review lens prompt no longer instructs a per-lens git fetch', () => {
  assert.doesNotMatch(lensPromptBody('runCodeReviewLens'), /git fetch origin main/);
});

test('bug-audit lens prompt no longer instructs a per-lens git fetch', () => {
  assert.doesNotMatch(lensPromptBody('runAuditLens'), /git fetch origin main/);
});

test('a single round-level prefetch step fetches origin/main before the parallel lenses', () => {
  assert.match(convergeSource, /function prefetchMainForRound\(/);
  const prefetchCallIndex = convergeSource.indexOf('await prefetchMainForRound(');
  const parallelLensIndex = convergeSource.indexOf('const lenses = await parallel(');
  assert.notEqual(prefetchCallIndex, -1, 'expected prefetchMainForRound to be invoked');
  assert.notEqual(parallelLensIndex, -1, 'expected the parallel lens block to exist');
  assert.ok(
    prefetchCallIndex < parallelLensIndex,
    'expected the round prefetch to run before the parallel lenses spawn',
  );
});

test('gotchas doc states parallel lenses must avoid concurrent git operations', () => {
  assert.doesNotMatch(gotchasSource, /cannot race on git state/);
  assert.match(gotchasSource, /fetch.*once.*before/i);
});
