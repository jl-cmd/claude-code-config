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
    ...overrides,
  };
}

test('an out-of-usage Copilot result (down) routes to the down kind', () => {
  const outcome = classifyCopilotOutcome(copilotResult({ clean: true, down: true }));
  assert.equal(outcome.kind, 'down');
});

test('a down Copilot result routes to down even when clean is false', () => {
  const outcome = classifyCopilotOutcome(copilotResult({ clean: false, down: true }));
  assert.equal(outcome.kind, 'down');
});

test('a dead Copilot gate agent retries rather than passing', () => {
  assert.equal(classifyCopilotOutcome(null).kind, 'retry');
});

test('a reachable Copilot gate with no findings and no clean verdict retries', () => {
  const outcome = classifyCopilotOutcome(copilotResult({ clean: false, down: false }));
  assert.equal(outcome.kind, 'retry');
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
  assert.doesNotMatch(
    schemaSource,
    /blocker:/,
    'the Copilot gate no longer surfaces a blocker; a down result carries the outage',
  );
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

test('the step-1 out-of-usage down-detection requires the notice commit_id to start with HEAD', () => {
  const copilotPrompt = functionBody('runCopilotGate');
  const stepOneStart = copilotPrompt.indexOf('`1.');
  assert.notEqual(stepOneStart, -1, 'expected a step-1 instruction in the gate prompt');
  const stepTwoStart = copilotPrompt.indexOf('`2.', stepOneStart);
  assert.notEqual(stepTwoStart, -1, 'expected a step-2 instruction in the gate prompt');
  const stepOneText = copilotPrompt.slice(stepOneStart, stepTwoStart);
  assert.match(
    stepOneText,
    /commit_id starts with \$\{head\}/,
    'expected step 1 to scope the out-of-usage notice to reviews whose commit_id starts with HEAD, matching step 2 and the convergence gate',
  );
});

test('a Copilot no-show after the poll cap returns a down result rather than a blocker', () => {
  const copilotPrompt = functionBody('runCopilotGate');
  const noReviewStart = copilotPrompt.indexOf('No review after');
  assert.notEqual(noReviewStart, -1, 'expected a no-show branch in the gate prompt');
  const noReviewBranch = copilotPrompt.slice(noReviewStart, noReviewStart + 200);
  assert.match(
    noReviewBranch,
    /down:\s*true/,
    'expected a Copilot no-show after the poll cap to return down:true',
  );
  assert.doesNotMatch(
    noReviewBranch,
    /blocker:/,
    'expected the no-show branch to carry a down result, not a blocker',
  );
});

test('checkConvergence wires the --copilot-down flag from a copilotDown argument', () => {
  const checkConvergenceBody = functionBody('checkConvergence');
  assert.match(
    checkConvergenceBody,
    /copilotDown \? ' --copilot-down' : ''/,
    'expected checkConvergence to append --copilot-down when copilotDown is set',
  );
  assert.match(
    checkConvergenceBody,
    /\$\{copilotDownFlag\}/,
    'expected the --copilot-down flag to be interpolated into the script invocation',
  );
});

test('the COPILOT phase routes a down outcome to FINALIZE with the gate bypassed', () => {
  const downBranchStart = convergeSource.indexOf("copilotOutcome.kind === 'down'");
  assert.notEqual(downBranchStart, -1, 'expected the COPILOT phase to handle a down outcome');
  const downBranch = convergeSource.slice(downBranchStart, downBranchStart + 400);
  assert.match(downBranch, /copilotDown = true/);
  assert.match(downBranch, /copilotNote =/);
  assert.match(downBranch, /phase = 'FINALIZE'/);
});
