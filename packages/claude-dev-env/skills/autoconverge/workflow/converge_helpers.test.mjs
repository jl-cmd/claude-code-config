import { test } from 'node:test';
import { strict as assert } from 'node:assert';

import {
    dedupeFindings,
    resolveBugbotDown,
    resolveRoundOutcome,
    detectFixProgress,
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
