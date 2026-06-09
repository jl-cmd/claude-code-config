const SEVERITY_RANK = { P0: 0, P1: 1, P2: 2 }
const SHA_COMPARISON_PREFIX_LENGTH = 7

/**
 * Dedup findings across lenses by file + line + lowercased title, reconciling
 * severity to the most severe duplicate, unioning detail text, and collecting
 * every distinct bot thread id so a collision never strands a review thread or
 * understates severity.
 * @param {Array<object>} allFindings concatenated lens findings
 * @returns {Array<object>} unique findings keyed by file:line:title
 */
export function dedupeFindings(allFindings) {
  const keptByFingerprint = new Map()
  const orderedFingerprints = []
  for (const eachFinding of allFindings) {
    const fingerprint = `${eachFinding.file}:${eachFinding.line}:${(eachFinding.title || '').toLowerCase()}`
    const alreadyKept = keptByFingerprint.get(fingerprint)
    if (alreadyKept === undefined) {
      keptByFingerprint.set(fingerprint, seedKeptFinding(eachFinding))
      orderedFingerprints.push(fingerprint)
      continue
    }
    mergeDuplicateInto(alreadyKept, eachFinding)
  }
  return orderedFingerprints.map((eachFingerprint) => keptByFingerprint.get(eachFingerprint))
}

/**
 * Build the first-seen finding for a fingerprint, seeding a thread-id list that
 * later duplicates extend.
 * @param {object} firstFinding the earliest finding at this fingerprint
 * @returns {object} a kept finding carrying a replyToCommentIds array
 */
function seedKeptFinding(firstFinding) {
  const seededThreadIds =
    firstFinding.replyToCommentId == null ? [] : [firstFinding.replyToCommentId]
  return { ...firstFinding, replyToCommentIds: seededThreadIds }
}

/**
 * Reconcile a dropped duplicate into the kept finding: raise severity to the
 * more severe of the two, union detail text, preserve the earliest thread id,
 * and append every distinct thread id for resolution.
 * @param {object} keptFinding the finding retained for this fingerprint
 * @param {object} droppedFinding the later duplicate being collapsed
 * @returns {void}
 */
function mergeDuplicateInto(keptFinding, droppedFinding) {
  if (isMoreSevere(droppedFinding.severity, keptFinding.severity)) {
    keptFinding.severity = droppedFinding.severity
  }
  if (keptFinding.replyToCommentId == null && droppedFinding.replyToCommentId != null) {
    keptFinding.replyToCommentId = droppedFinding.replyToCommentId
  }
  if (droppedFinding.replyToCommentId != null && !keptFinding.replyToCommentIds.includes(droppedFinding.replyToCommentId)) {
    keptFinding.replyToCommentIds.push(droppedFinding.replyToCommentId)
  }
  const droppedDetail = droppedFinding.detail || ''
  const keptDetail = keptFinding.detail || ''
  if (droppedDetail && !keptDetail.includes(droppedDetail)) {
    keptFinding.detail = keptDetail ? `${keptDetail}\n${droppedDetail}` : droppedDetail
  }
}

/**
 * Collect every distinct GitHub review thread id a finding carries, preferring
 * the deduped replyToCommentIds list and falling back to the scalar
 * replyToCommentId for findings that never passed through dedupeFindings.
 * @param {object} finding a single finding
 * @returns {Array<number>} distinct non-null thread ids to reply to and resolve
 */
export function collectFindingThreadIds(finding) {
  if (Array.isArray(finding.replyToCommentIds)) {
    return finding.replyToCommentIds.filter((eachId) => eachId != null)
  }
  return finding.replyToCommentId == null ? [] : [finding.replyToCommentId]
}

/**
 * Decide whether a candidate severity outranks the current one (P0 > P1 > P2).
 * @param {string} candidateSeverity the duplicate's severity
 * @param {string} currentSeverity the kept finding's severity
 * @returns {boolean} true when the candidate is strictly more severe
 */
function isMoreSevere(candidateSeverity, currentSeverity) {
  const candidateRank = SEVERITY_RANK[candidateSeverity]
  const currentRank = SEVERITY_RANK[currentSeverity]
  if (candidateRank === undefined) return false
  if (currentRank === undefined) return true
  return candidateRank < currentRank
}

/**
 * Decide whether the convergence check should bypass the Bugbot gate this round,
 * recomputed from the current Bugbot lens result rather than latched across the
 * run, so a recovered Bugbot re-arms the gate. A dead lens agent (null/undefined
 * result) produces no Bugbot verdict on this HEAD, so it is treated as down to
 * keep the convergence gate from demanding a verdict that cannot exist.
 * @param {object|null|undefined} bugbotLens the current round's Bugbot lens result
 * @param {boolean} bugbotDisabled true when Bugbot is opted out for the whole run
 * @returns {boolean} true when the Bugbot gate is bypassed for the current HEAD
 */
export function resolveBugbotDown(bugbotLens, bugbotDisabled) {
  if (bugbotDisabled) return true
  if (bugbotLens == null) return true
  return bugbotLens.down === true
}

/**
 * Decide whether a single surviving lens calls the HEAD clean. A lens is clean
 * when it explicitly reports clean:true, or when it is bypassed (down:true) so it
 * has no verdict to withhold. A lens reporting clean:false with no findings — a
 * Bugbot lens awaiting a pending CI verdict, or a reviewer that reports 'not
 * clean' without pinning a file:line — keeps the round in the converge phase.
 * @param {object} lens a surviving LENS_SCHEMA result
 * @returns {boolean} true when this lens does not hold the round back
 */
function lensCallsHeadClean(lens) {
  return lens.clean === true || lens.down === true
}

/**
 * Decide the outcome of a converge round from its raw parallel lens results:
 * whether every lens agent died (a failed round that must not post a clean
 * artifact), the deduped findings from the surviving lenses, and whether the
 * round is clean. A round is clean only when at least one lens survived, every
 * surviving lens calls the HEAD clean, and the deduped findings are empty — so a
 * clean:false lens with zero findings keeps the round converging rather than
 * advancing to the Copilot gate on a HEAD a lens did not call clean.
 * @param {Array<object|null>} lensResults raw parallel results, null per dead lens
 * @returns {{allLensesDead: boolean, findings: Array<object>, roundClean: boolean}} round outcome
 */
export function resolveRoundOutcome(lensResults) {
  const liveLenses = lensResults.filter(Boolean)
  const findings = dedupeFindings(liveLenses.flatMap((eachLens) => eachLens.findings || []))
  const allLensesDead = liveLenses.length === 0
  const everyLensClean = liveLenses.every(lensCallsHeadClean)
  const roundClean = !allLensesDead && everyLensClean && findings.length === 0
  return { allLensesDead, findings, roundClean }
}

/**
 * Reduce a SHA to a case-folded common prefix so a full 40-char HEAD and an
 * abbreviated SHA reported by a fix agent (git rev-parse --short) for the same
 * commit compare equal. A non-string SHA folds to the empty string.
 * @param {string} sha a full or abbreviated commit SHA
 * @returns {string} the lowercased leading prefix used for comparison
 */
function normalizeShaForComparison(sha) {
  if (typeof sha !== 'string') return ''
  return sha.slice(0, SHA_COMPARISON_PREFIX_LENGTH).toLowerCase()
}

/**
 * Decide whether a fix lens actually advanced the round: a pushed fix that moved
 * HEAD progressed, and so did an all-stale round whose findings were every one
 * already addressed — the fix lens makes no commit but resolves each thread and
 * reports resolvedWithoutCommit:true, leaving HEAD unchanged on purpose. A null
 * result, a no-push round that did not resolve every thread, or a SHA equal to
 * the prior HEAD on a case-folded common prefix did not progress and must surface
 * a distinct fix-stalled blocker. Comparing on a normalized prefix keeps a no-op
 * fix that reports an abbreviated SHA of the unchanged HEAD from masquerading as
 * a moved-HEAD push.
 * @param {object|null} fixResult the FIX_SCHEMA result, or null on agent failure
 * @param {string} priorHead the HEAD the fix was applied against
 * @returns {{progressed: boolean, newSha: string}} progress decision and resulting HEAD
 */
export function detectFixProgress(fixResult, priorHead) {
  if (fixResult == null) return { progressed: false, newSha: priorHead }
  const newSha = fixResult.newSha || priorHead
  if (fixResult.resolvedWithoutCommit === true) {
    return { progressed: true, newSha: priorHead }
  }
  const movedHead = normalizeShaForComparison(newSha) !== normalizeShaForComparison(priorHead)
  const progressed = fixResult.pushed === true && movedHead
  return { progressed, newSha }
}

/**
 * Decide whether a resolved HEAD SHA is safe to spawn lenses against. A dead
 * resolve-head agent or a malformed result yields a falsy SHA; spawning lenses
 * against it interpolates the literal string 'HEAD undefined' into their prompts
 * and produces a spurious clean verdict on a non-existent commit.
 * @param {string|null|undefined} resolvedHead the SHA from resolveHead()
 * @returns {boolean} true only when the SHA is a non-empty string
 */
export function isResolvedHeadUsable(resolvedHead) {
  return typeof resolvedHead === 'string' && resolvedHead.length > 0
}

/**
 * Classify a Copilot gate result into the loop's next action. A dead gate agent
 * (null result) is a retry rather than an approval, mirroring the converge
 * lenses' dead-agent convention so a failed gate is never mistaken for a clean
 * Copilot review. A non-null blocker ends the run; findings route to a fix step;
 * a clean result approves the gate.
 * @param {object|null|undefined} copilot the COPILOT_SCHEMA result, or null on agent failure
 * @returns {{kind: string, blocker?: string, findings?: Array<object>}} the next action
 */
export function classifyCopilotOutcome(copilot) {
  if (copilot == null) return { kind: 'retry' }
  if (copilot.blocker) return { kind: 'blocker', blocker: copilot.blocker }
  if (copilot.findings.length > 0) return { kind: 'fix', findings: copilot.findings }
  return { kind: 'approved' }
}

/**
 * Decide whether the mark-ready step actually cleared the draft state. The run
 * reports converged only when the mark-ready agent confirms ready:true; a dead
 * agent (null result) or a ready:false report means `gh pr ready` did not land
 * (auth or token drift, a transient gh failure), so the PR is still a draft and
 * the run must surface a blocker rather than claim success.
 * @param {object|null|undefined} readyResult the READY_SCHEMA result, or null on agent failure
 * @returns {{converged: boolean, blocker: string|null}} convergence decision
 */
export function classifyReadyOutcome(readyResult) {
  if (readyResult != null && readyResult.ready === true) {
    return { converged: true, blocker: null }
  }
  return {
    converged: false,
    blocker: 'mark-ready step did not confirm the PR left draft state (gh pr ready failed or the agent died)',
  }
}

/**
 * Normalize the workflow's raw args global into a run-coordinates object. The
 * Workflow runtime delivers args as a JSON-encoded string, so a string payload
 * is parsed; an object payload passes through unchanged. Reading args.owner off
 * an unparsed string yields undefined and strands every GitHub call on invalid
 * coordinates, so every entry point reads coordinates through this function.
 * @param {string|object} rawArgs the workflow args global (JSON string or object)
 * @returns {object} the run coordinates ({owner, repo, prNumber, bugbotDisabled})
 */
export function normalizeRunInput(rawArgs) {
  return typeof rawArgs === 'string' ? JSON.parse(rawArgs) : rawArgs
}
