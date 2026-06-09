import { test } from 'node:test';
import { strict as assert } from 'node:assert';

import { classifyCopilotOutcome, classifyConvergenceOutcome } from './decisions.mjs';

test('classifyCopilotOutcome retries when the gate agent died (null result)', () => {
  assert.deepEqual(classifyCopilotOutcome(null), { kind: 'retry' });
  assert.deepEqual(classifyCopilotOutcome(undefined), { kind: 'retry' });
});

test('classifyCopilotOutcome ends the run when a blocker is present', () => {
  const copilotResult = { sha: 'abc', clean: false, findings: [], blocker: 'Copilot no-show' };
  assert.deepEqual(classifyCopilotOutcome(copilotResult), {
    kind: 'blocker',
    blocker: 'Copilot no-show',
  });
});

test('classifyCopilotOutcome routes to fix when Copilot raised findings', () => {
  const eachFinding = { file: 'a.js', line: 1, severity: 'P1', title: 't', detail: 'd', replyToCommentId: 7 };
  const copilotResult = { sha: 'abc', clean: false, findings: [eachFinding], blocker: null };
  assert.deepEqual(classifyCopilotOutcome(copilotResult), {
    kind: 'fix',
    findings: [eachFinding],
  });
});

test('classifyCopilotOutcome approves only when the gate reports clean with no findings', () => {
  const cleanResult = { sha: 'abc', clean: true, findings: [], blocker: null };
  assert.deepEqual(classifyCopilotOutcome(cleanResult), { kind: 'approved' });
});

test('classifyCopilotOutcome retries an unreliable gate that reports clean:false with no findings', () => {
  const malformedResult = { sha: 'abc', clean: false, findings: [], blocker: null };
  assert.deepEqual(classifyCopilotOutcome(malformedResult), { kind: 'retry' });
});

test('classifyConvergenceOutcome retries when the check agent died (null result)', () => {
  assert.deepEqual(classifyConvergenceOutcome(null), { kind: 'retry' });
  assert.deepEqual(classifyConvergenceOutcome(undefined), { kind: 'retry' });
});

test('classifyConvergenceOutcome marks ready when the gate passed', () => {
  assert.deepEqual(classifyConvergenceOutcome({ pass: true, failures: [] }), { kind: 'ready' });
});

test('classifyConvergenceOutcome repairs only on a real FAIL with reported failures', () => {
  const failedCheck = { pass: false, failures: ['FAIL bugbot gate'] };
  assert.deepEqual(classifyConvergenceOutcome(failedCheck), {
    kind: 'repair',
    failures: ['FAIL bugbot gate'],
  });
});

test('classifyConvergenceOutcome retries a pass:false report carrying no failure lines', () => {
  assert.deepEqual(classifyConvergenceOutcome({ pass: false, failures: [] }), { kind: 'retry' });
});
