const SEVERITY_RANK = { P0: 0, P1: 1, P2: 2 }

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
 * Decide the outcome of a converge round from its raw parallel lens results:
 * whether every lens agent died (a failed round that must not post a clean
 * artifact) and the deduped findings from the surviving lenses.
 * @param {Array<object|null>} lensResults raw parallel results, null per dead lens
 * @returns {{allLensesDead: boolean, findings: Array<object>}} round outcome
 */
export function resolveRoundOutcome(lensResults) {
  const liveLenses = lensResults.filter(Boolean)
  const findings = dedupeFindings(liveLenses.flatMap((eachLens) => eachLens.findings || []))
  return { allLensesDead: liveLenses.length === 0, findings }
}

/**
 * Decide whether a fix lens actually landed a fix on the PR branch: a pushed fix
 * that moved HEAD progressed; a null result, an unpushed result, or an unchanged
 * SHA did not and must surface a distinct fix-stalled blocker.
 * @param {object|null} fixResult the FIX_SCHEMA result, or null on agent failure
 * @param {string} priorHead the HEAD the fix was applied against
 * @returns {{progressed: boolean, newSha: string}} progress decision and resulting HEAD
 */
export function detectFixProgress(fixResult, priorHead) {
  if (fixResult == null) return { progressed: false, newSha: priorHead }
  const newSha = fixResult.newSha || priorHead
  const progressed = fixResult.pushed === true && newSha !== priorHead
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
