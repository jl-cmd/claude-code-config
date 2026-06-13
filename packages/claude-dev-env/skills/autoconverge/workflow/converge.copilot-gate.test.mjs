import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const convergeSource = readFileSync(join(workflowDirectory, 'converge.mjs'), 'utf8');

function functionBody(functionName) {
  const functionStart = convergeSource.indexOf(`function ${functionName}(`);
  assert.notEqual(functionStart, -1, `expected ${functionName} to exist`);
  const nextFunctionStart = convergeSource.indexOf('\nfunction ', functionStart + 1);
  const functionEnd = nextFunctionStart === -1 ? convergeSource.length : nextFunctionStart;
  return convergeSource.slice(functionStart, functionEnd);
}

const productionModule = new Function(
  `${functionBody('classifyCopilotOutcome')}\n` +
    'return { classifyCopilotOutcome };',
)();
const { classifyCopilotOutcome } = productionModule;

function copilotResult(overrides) {
  return {
    sha: 'abcdef0',
    clean: false,
    down: false,
    findings: [],
    blocker: null,
    ...overrides,
  };
}

test('an out-of-usage Copilot result (down) passes the gate as approved', () => {
  const outcome = classifyCopilotOutcome(copilotResult({ clean: true, down: true }));
  assert.equal(outcome.kind, 'approved');
});

test('a down Copilot result passes even when clean is false', () => {
  const outcome = classifyCopilotOutcome(copilotResult({ clean: false, down: true }));
  assert.equal(outcome.kind, 'approved');
});

test('a dead Copilot gate agent retries rather than passing', () => {
  assert.equal(classifyCopilotOutcome(null).kind, 'retry');
});

test('a no-show blocker still ends the run when Copilot is not down', () => {
  const outcome = classifyCopilotOutcome(
    copilotResult({ blocker: 'Copilot did not surface a review on HEAD after 6 polls' }),
  );
  assert.equal(outcome.kind, 'blocker');
});

test('Copilot findings route to a fix when Copilot is reachable and not down', () => {
  const outcome = classifyCopilotOutcome(
    copilotResult({
      findings: [
        {
          file: 'a.py',
          line: 1,
          severity: 'P1',
          category: 'bug',
          title: 't',
          detail: 'd',
          replyToCommentId: null,
        },
      ],
    }),
  );
  assert.equal(outcome.kind, 'fix');
});

test('COPILOT_SCHEMA carries a required down field', () => {
  const schemaStart = convergeSource.indexOf('const COPILOT_SCHEMA =');
  const schemaEnd = convergeSource.indexOf('const HEAD_SCHEMA =');
  assert.notEqual(schemaStart, -1, 'expected COPILOT_SCHEMA to exist');
  const schemaSource = convergeSource.slice(schemaStart, schemaEnd);
  assert.match(schemaSource, /down:\s*\{\s*type:\s*'boolean'/);
  assert.match(schemaSource, /required:\s*\[[^\]]*'down'[^\]]*\]/);
});

test('the Copilot gate prompt detects an out-of-usage notice and returns a down result', () => {
  const copilotPrompt = functionBody('runCopilotGate');
  assert.match(
    copilotPrompt,
    /quota|out of usage|out-of-usage/i,
    'expected the gate to name the out-of-usage / quota signal',
  );
  assert.match(
    copilotPrompt,
    /down:\s*true/,
    'expected the gate to return down:true on an out-of-usage notice',
  );
});
