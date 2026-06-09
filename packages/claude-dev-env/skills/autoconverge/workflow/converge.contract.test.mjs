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

test('bugbot lens preamble does not blanket-instruct passing --owner/--repo to every script', () => {
  const bugbotPrompt = lensPromptBody('runBugbotLens');
  assert.doesNotMatch(
    bugbotPrompt,
    /use the existing scripts; pass --owner/,
    'the blanket clause breaks reviews_disabled.py, which accepts only --reviewer',
  );
});

test('bugbot lens invokes reviews_disabled.py with only --reviewer', () => {
  const bugbotPrompt = lensPromptBody('runBugbotLens');
  const reviewsDisabledIndex = bugbotPrompt.indexOf('reviews_disabled.py');
  assert.notEqual(reviewsDisabledIndex, -1, 'expected reviews_disabled.py invocation');
  const invocationLineEnd = bugbotPrompt.indexOf('\\n', reviewsDisabledIndex);
  const invocationLine = bugbotPrompt.slice(reviewsDisabledIndex, invocationLineEnd);
  assert.match(invocationLine, /--reviewer bugbot/);
  assert.doesNotMatch(
    invocationLine,
    /--owner|--repo/,
    'reviews_disabled.py argparse rejects --owner/--repo with SystemExit(2)',
  );
});

test('gotchas doc states parallel lenses must avoid concurrent git operations', () => {
  assert.doesNotMatch(gotchasSource, /cannot race on git state/);
  assert.match(gotchasSource, /fetch.*once.*before/i);
});
