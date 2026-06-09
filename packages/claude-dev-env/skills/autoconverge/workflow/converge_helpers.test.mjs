import { test } from 'node:test';
import { strict as assert } from 'node:assert';

import { dedupeFindings, resolveBugbotDown } from './converge_helpers.mjs';


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


test('resolveBugbotDown treats a missing Bugbot lens as not down on an enabled run', () => {
    const missingLens = undefined;

    assert.equal(resolveBugbotDown(missingLens, false), false);
});
