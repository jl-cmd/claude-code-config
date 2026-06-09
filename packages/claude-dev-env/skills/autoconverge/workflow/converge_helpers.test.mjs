import { test } from 'node:test';
import { strict as assert } from 'node:assert';

import {
    dedupeFindings,
    resolveBugbotDown,
    resolveRoundOutcome,
    detectFixProgress,
    isResolvedHeadUsable,
    classifyCopilotOutcome,
    classifyReadyOutcome,
    normalizeRunInput,
} from './converge_helpers.mjs';


test('dedupeFindings carries a dropped duplicate\'s thread id onto the kept finding', () => {
    const firstFindingWithoutThread = {
        file: 'converge.mjs',
        line: 301,
        severity: 'P1',
        title: 'Stranded thread',
        detail: 'audit copy',
        replyToCommentId: null,
    };
    const duplicateWithThread = {
        file: 'converge.mjs',
        line: 301,
        severity: 'P1',
        title: 'stranded thread',
        detail: 'bugbot copy',
        replyToCommentId: 12345,
    };

    const uniqueFindings = dedupeFindings([firstFindingWithoutThread, duplicateWithThread]);

    assert.equal(uniqueFindings.length, 1);
    assert.equal(uniqueFindings[0].replyToCommentId, 12345);
});


test('dedupeFindings keeps the earliest thread id when both duplicates carry one', () => {
    const firstFindingWithThread = {
        file: 'converge.mjs',
        line: 50,
        severity: 'P2',
        title: 'Same spot',
        detail: 'first',
        replyToCommentId: 111,
    };
    const duplicateWithDifferentThread = {
        file: 'converge.mjs',
        line: 50,
        severity: 'P2',
        title: 'same spot',
        detail: 'second',
        replyToCommentId: 222,
    };

    const uniqueFindings = dedupeFindings([firstFindingWithThread, duplicateWithDifferentThread]);

    assert.equal(uniqueFindings.length, 1);
    assert.equal(uniqueFindings[0].replyToCommentId, 111);
});


test('dedupeFindings surfaces every distinct thread id when duplicates collide', () => {
    const firstFindingWithThread = {
        file: 'converge.mjs',
        line: 50,
        severity: 'P2',
        title: 'Same spot',
        detail: 'first',
        replyToCommentId: 111,
    };
    const duplicateWithDifferentThread = {
        file: 'converge.mjs',
        line: 50,
        severity: 'P2',
        title: 'same spot',
        detail: 'second',
        replyToCommentId: 222,
    };

    const uniqueFindings = dedupeFindings([firstFindingWithThread, duplicateWithDifferentThread]);

    assert.deepEqual(uniqueFindings[0].replyToCommentIds, [111, 222]);
});


test('dedupeFindings raises the kept finding to the more severe duplicate', () => {
    const lowSeverityFirst = {
        file: 'converge.mjs',
        line: 303,
        severity: 'P2',
        title: 'Severity collapse',
        detail: 'code-review copy',
        replyToCommentId: null,
    };
    const highSeverityDuplicate = {
        file: 'converge.mjs',
        line: 303,
        severity: 'P0',
        title: 'severity collapse',
        detail: 'audit copy',
        replyToCommentId: null,
    };

    const uniqueFindings = dedupeFindings([lowSeverityFirst, highSeverityDuplicate]);

    assert.equal(uniqueFindings.length, 1);
    assert.equal(uniqueFindings[0].severity, 'P0');
});


test('dedupeFindings unions detail text from a dropped duplicate', () => {
    const firstFinding = {
        file: 'app.py',
        line: 10,
        severity: 'P2',
        title: 'Overlap',
        detail: 'kept detail',
        replyToCommentId: null,
    };
    const duplicateFinding = {
        file: 'app.py',
        line: 10,
        severity: 'P2',
        title: 'overlap',
        detail: 'extra detail',
        replyToCommentId: null,
    };

    const uniqueFindings = dedupeFindings([firstFinding, duplicateFinding]);

    assert.equal(uniqueFindings.length, 1);
    assert.ok(uniqueFindings[0].detail.includes('kept detail'));
    assert.ok(uniqueFindings[0].detail.includes('extra detail'));
});


test('dedupeFindings keeps findings at distinct file:line:title fingerprints', () => {
    const findingOne = {
        file: 'a.py',
        line: 1,
        severity: 'P1',
        title: 'One',
        detail: 'd1',
        replyToCommentId: null,
    };
    const findingTwo = {
        file: 'a.py',
        line: 2,
        severity: 'P1',
        title: 'Two',
        detail: 'd2',
        replyToCommentId: null,
    };

    const uniqueFindings = dedupeFindings([findingOne, findingTwo]);

    assert.equal(uniqueFindings.length, 2);
});


test('resolveBugbotDown reports down when the current Bugbot lens is down', () => {
    const bugbotLensDown = { sha: 'abc', clean: true, down: true, findings: [] };

    assert.equal(resolveBugbotDown(bugbotLensDown, false), true);
});


test('resolveBugbotDown clears down when a later round Bugbot lens recovers', () => {
    const bugbotLensRecovered = { sha: 'abc', clean: false, down: false, findings: [] };

    assert.equal(resolveBugbotDown(bugbotLensRecovered, false), false);
});


test('resolveBugbotDown stays down for a run where Bugbot is opted out', () => {
    const bugbotLensDisabled = { sha: 'abc', clean: true, down: true, findings: [] };

    assert.equal(resolveBugbotDown(bugbotLensDisabled, true), true);

    const missingLens = undefined;

    assert.equal(resolveBugbotDown(missingLens, true), true);
});


test('resolveBugbotDown treats a dead Bugbot lens as down on an enabled run', () => {
    const deadLens = null;

    assert.equal(resolveBugbotDown(deadLens, false), true);

    const missingLens = undefined;

    assert.equal(resolveBugbotDown(missingLens, false), true);
});


test('resolveRoundOutcome marks a total lens wipeout as a failed round', () => {
    const allLensesDead = [null, null, null];

    const outcome = resolveRoundOutcome(allLensesDead);

    assert.equal(outcome.allLensesDead, true);
    assert.equal(outcome.findings.length, 0);
});


test('resolveRoundOutcome dedupes findings across the surviving lenses', () => {
    const lensesWithOneSurvivor = [
        null,
        { findings: [{ file: 'a.py', line: 1, severity: 'P1', title: 'One', detail: 'd', replyToCommentId: null }] },
        { findings: [{ file: 'a.py', line: 1, severity: 'P0', title: 'one', detail: 'd2', replyToCommentId: null }] },
    ];

    const outcome = resolveRoundOutcome(lensesWithOneSurvivor);

    assert.equal(outcome.allLensesDead, false);
    assert.equal(outcome.findings.length, 1);
    assert.equal(outcome.findings[0].severity, 'P0');
});


test('resolveRoundOutcome calls a round clean only when every surviving lens reports clean or down', () => {
    const everyLensClean = [
        { clean: true, down: false, findings: [] },
        { clean: true, down: false, findings: [] },
        { clean: true, down: true, findings: [] },
    ];

    const outcome = resolveRoundOutcome(everyLensClean);

    assert.equal(outcome.roundClean, true);
    assert.equal(outcome.findings.length, 0);
});


test('resolveRoundOutcome keeps a not-clean lens with zero findings in the converge phase', () => {
    const oneLensNotCleanWithoutFindings = [
        { clean: true, down: false, findings: [] },
        { clean: false, down: false, findings: [] },
        { clean: true, down: false, findings: [] },
    ];

    const outcome = resolveRoundOutcome(oneLensNotCleanWithoutFindings);

    assert.equal(outcome.roundClean, false);
    assert.equal(outcome.findings.length, 0);
});


test('resolveRoundOutcome reports a round with findings as not clean', () => {
    const oneLensWithFindings = [
        { clean: false, down: false, findings: [{ file: 'a.py', line: 1, severity: 'P1', title: 'One', detail: 'd', replyToCommentId: null }] },
        { clean: true, down: false, findings: [] },
        { clean: true, down: false, findings: [] },
    ];

    const outcome = resolveRoundOutcome(oneLensWithFindings);

    assert.equal(outcome.roundClean, false);
    assert.equal(outcome.findings.length, 1);
});


test('resolveRoundOutcome reports a total lens wipeout as not clean', () => {
    const allLensesDead = [null, null, null];

    const outcome = resolveRoundOutcome(allLensesDead);

    assert.equal(outcome.roundClean, false);
});


test('detectFixProgress flags a fix lens that never pushed', () => {
    const notPushed = { newSha: 'sameheadsha', pushed: false, summary: '' };

    assert.equal(detectFixProgress(notPushed, 'sameheadsha').progressed, false);
});


test('detectFixProgress flags a fix lens that returned the unchanged HEAD', () => {
    const unchangedHead = { newSha: 'sameheadsha', pushed: true, summary: 'noop' };

    assert.equal(detectFixProgress(unchangedHead, 'sameheadsha').progressed, false);
});


test('detectFixProgress flags a null fix result', () => {
    assert.equal(detectFixProgress(null, 'sameheadsha').progressed, false);
});


test('detectFixProgress accepts a pushed fix that moved HEAD', () => {
    const moved = { newSha: 'newheadsha', pushed: true, summary: 'fixed' };

    const progress = detectFixProgress(moved, 'oldheadsha');

    assert.equal(progress.progressed, true);
    assert.equal(progress.newSha, 'newheadsha');
});


test('detectFixProgress flags a Copilot fix lens that never pushed', () => {
    const copilotFixNotPushed = { newSha: '', pushed: false, summary: '' };

    assert.equal(detectFixProgress(copilotFixNotPushed, 'copilotheadsha').progressed, false);
});


test('detectFixProgress accepts a pushed Copilot fix that moved HEAD to a new SHA', () => {
    const copilotFixMoved = { newSha: 'b1c2d3e4f5a6978cabbee01234567890deadbeef', pushed: true, summary: 'fixed copilot finding' };

    const progress = detectFixProgress(copilotFixMoved, 'a58fee90c20dbe2441b1079175c11eb08d674fa6');

    assert.equal(progress.progressed, true);
    assert.equal(progress.newSha, 'b1c2d3e4f5a6978cabbee01234567890deadbeef');
});


test('detectFixProgress treats an abbreviated SHA of the unchanged HEAD as a no-op stall', () => {
    const fullPriorHead = 'a58fee90c20dbe2441b1079175c11eb08d674fa6';
    const abbreviatedSameCommit = { newSha: 'a58fee9', pushed: true, summary: 'no code change, thread resolved' };

    const progress = detectFixProgress(abbreviatedSameCommit, fullPriorHead);

    assert.equal(progress.progressed, false);
});


test('detectFixProgress ignores SHA case when comparing the new HEAD against the prior HEAD', () => {
    const fullPriorHead = 'A58FEE90C20DBE2441B1079175C11EB08D674FA6';
    const lowercaseSameCommit = { newSha: 'a58fee90c20dbe2441b1079175c11eb08d674fa6', pushed: true, summary: 'noop' };

    const progress = detectFixProgress(lowercaseSameCommit, fullPriorHead);

    assert.equal(progress.progressed, false);
});


test('detectFixProgress accepts an abbreviated SHA that differs from the prior HEAD prefix', () => {
    const fullPriorHead = 'a58fee90c20dbe2441b1079175c11eb08d674fa6';
    const abbreviatedNewCommit = { newSha: 'b1c2d3e', pushed: true, summary: 'real fix' };

    const progress = detectFixProgress(abbreviatedNewCommit, fullPriorHead);

    assert.equal(progress.progressed, true);
    assert.equal(progress.newSha, 'b1c2d3e');
});


test('detectFixProgress treats an all-stale round that resolved threads without a commit as progress', () => {
    const fullPriorHead = 'a58fee90c20dbe2441b1079175c11eb08d674fa6';
    const resolvedWithoutCommit = {
        newSha: fullPriorHead,
        pushed: false,
        resolvedWithoutCommit: true,
        summary: 'every finding was already addressed; threads resolved, no code change',
    };

    const progress = detectFixProgress(resolvedWithoutCommit, fullPriorHead);

    assert.equal(progress.progressed, true);
    assert.equal(progress.newSha, fullPriorHead);
});


test('detectFixProgress still stalls a no-push round that did not resolve every thread', () => {
    const fullPriorHead = 'a58fee90c20dbe2441b1079175c11eb08d674fa6';
    const unresolvedNoPush = {
        newSha: fullPriorHead,
        pushed: false,
        resolvedWithoutCommit: false,
        summary: 'fix failed',
    };

    const progress = detectFixProgress(unresolvedNoPush, fullPriorHead);

    assert.equal(progress.progressed, false);
});


test('isResolvedHeadUsable rejects an undefined HEAD from a dead resolve-head agent', () => {
    assert.equal(isResolvedHeadUsable(undefined), false);
});


test('isResolvedHeadUsable rejects a null HEAD', () => {
    assert.equal(isResolvedHeadUsable(null), false);
});


test('isResolvedHeadUsable rejects an empty-string HEAD', () => {
    assert.equal(isResolvedHeadUsable(''), false);
});


test('isResolvedHeadUsable accepts a real 40-character HEAD SHA', () => {
    const fortyCharacterSha = 'a58fee90c20dbe2441b1079175c11eb08d674fa6';

    assert.equal(isResolvedHeadUsable(fortyCharacterSha), true);
});


test('classifyCopilotOutcome marks a dead Copilot gate (null result) for retry', () => {
    const deadGate = null;

    const outcome = classifyCopilotOutcome(deadGate);

    assert.equal(outcome.kind, 'retry');
});


test('classifyCopilotOutcome surfaces a Copilot blocker', () => {
    const timedOut = { sha: 'abc', clean: false, findings: [], blocker: 'Copilot did not surface a review on HEAD after 3 polls' };

    const outcome = classifyCopilotOutcome(timedOut);

    assert.equal(outcome.kind, 'blocker');
    assert.equal(outcome.blocker, 'Copilot did not surface a review on HEAD after 3 polls');
});


test('classifyCopilotOutcome routes Copilot findings into a fix step', () => {
    const withFindings = {
        sha: 'abc',
        clean: false,
        findings: [{ file: 'a.py', line: 1, severity: 'P1', title: 'One', detail: 'd', replyToCommentId: 99 }],
        blocker: null,
    };

    const outcome = classifyCopilotOutcome(withFindings);

    assert.equal(outcome.kind, 'fix');
    assert.equal(outcome.findings.length, 1);
});


test('classifyCopilotOutcome treats a clean Copilot review as approved', () => {
    const cleanGate = { sha: 'abc', clean: true, findings: [], blocker: null };

    const outcome = classifyCopilotOutcome(cleanGate);

    assert.equal(outcome.kind, 'approved');
});


test('classifyReadyOutcome confirms convergence when the PR is marked ready', () => {
    const markedReady = { ready: true };

    assert.equal(classifyReadyOutcome(markedReady).converged, true);
});


test('classifyReadyOutcome blocks convergence when the mark-ready agent reports not ready', () => {
    const stillDraft = { ready: false };

    const outcome = classifyReadyOutcome(stillDraft);

    assert.equal(outcome.converged, false);
    assert.ok(outcome.blocker.length > 0);
});


test('classifyReadyOutcome blocks convergence when the mark-ready agent died', () => {
    const deadAgent = null;

    const outcome = classifyReadyOutcome(deadAgent);

    assert.equal(outcome.converged, false);
    assert.ok(outcome.blocker.length > 0);
});


test('normalizeRunInput parses a JSON-string args payload into run coordinates', () => {
    const stringifiedArgs = JSON.stringify({ owner: 'jl-cmd', repo: 'claude-code-config', prNumber: 543, bugbotDisabled: false });

    const runInput = normalizeRunInput(stringifiedArgs);

    assert.equal(runInput.owner, 'jl-cmd');
    assert.equal(runInput.repo, 'claude-code-config');
    assert.equal(runInput.prNumber, 543);
    assert.equal(runInput.bugbotDisabled, false);
});


test('normalizeRunInput passes an object args payload through unchanged', () => {
    const objectArgs = { owner: 'jl-cmd', repo: 'claude-code-config', prNumber: 543, bugbotDisabled: false };

    const runInput = normalizeRunInput(objectArgs);

    assert.equal(runInput, objectArgs);
});
