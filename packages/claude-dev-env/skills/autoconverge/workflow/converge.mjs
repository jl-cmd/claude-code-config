import {
  resolveBugbotDown,
  resolveRoundOutcome,
  detectFixProgress,
  collectFindingThreadIds,
  isResolvedHeadUsable,
  classifyCopilotOutcome,
} from './converge_helpers.mjs'

export const meta = {
  name: 'autoconverge',
  description: 'Drive one draft PR to convergence in a single autonomous run: parallel Bugbot + code-review + bug-audit lenses on the same HEAD each round, dedup findings, fix once, re-verify, then a Copilot wait-gate and a final convergence check that marks the PR ready.',
  whenToUse: 'Launched by the /autoconverge skill after it resolves PR scope, enters a worktree, and grants project .claude permissions.',
  phases: [
    { title: 'Converge', detail: 'Bugbot + code-review + bug-audit in parallel each round; one clean-coder applies all fixes; loop until all three are clean on a stable HEAD' },
    { title: 'Copilot gate', detail: 'Request Copilot review and poll up to three times; route findings back into Converge' },
    { title: 'Finalize', detail: 'Run check_convergence.py; mark draft=false on a full pass' },
  ],
}

const CONFIG = {
  maxRounds: 20,
  copilotMaxPolls: 3,
  sharedScripts: '$HOME/.claude/skills/pr-converge/scripts',
  prLoopScripts: '$HOME/.claude/_shared/pr-loop/scripts',
  bugteamRubric: '$HOME/.claude/skills/bugteam/reference/audit-contract.md',
}

const LENS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    sha: { type: 'string', description: 'PR HEAD SHA this lens evaluated' },
    clean: { type: 'boolean', description: 'true when this lens found no findings on sha' },
    down: { type: 'boolean', description: 'true when the reviewer is opted out or unreachable and is bypassed' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          severity: { type: 'string', enum: ['P0', 'P1', 'P2'] },
          title: { type: 'string' },
          detail: { type: 'string' },
          replyToCommentId: { type: ['integer', 'null'], description: 'GitHub review comment id to reply to and resolve, or null when the finding has no thread' },
        },
        required: ['file', 'line', 'severity', 'title', 'detail', 'replyToCommentId'],
      },
    },
  },
  required: ['sha', 'clean', 'down', 'findings'],
}

const COPILOT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    sha: { type: 'string' },
    clean: { type: 'boolean' },
    findings: LENS_SCHEMA.properties.findings,
    blocker: { type: ['string', 'null'], description: 'non-null when Copilot never surfaced a review after the poll cap' },
  },
  required: ['sha', 'clean', 'findings', 'blocker'],
}

const HEAD_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: { sha: { type: 'string' } },
  required: ['sha'],
}

const FIX_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    newSha: { type: 'string', description: 'HEAD SHA after the fix commit was pushed' },
    pushed: { type: 'boolean' },
    summary: { type: 'string' },
  },
  required: ['newSha', 'pushed', 'summary'],
}

const CONVERGENCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    pass: { type: 'boolean', description: 'true only when check_convergence.py exits 0' },
    failures: { type: 'array', items: { type: 'string' }, description: 'FAIL lines from check_convergence.py when pass is false' },
  },
  required: ['pass', 'failures'],
}

const prCoordinates = `owner=${args.owner} repo=${args.repo} PR #${args.prNumber} (https://github.com/${args.owner}/${args.repo}/pull/${args.prNumber})`
const bugbotDisabledNote = args.bugbotDisabled
  ? 'Cursor Bugbot is opted out for this run; treat the Bugbot lens as down without triggering or polling it.'
  : 'Cursor Bugbot participates this run.'

/**
 * Resolve the current PR HEAD SHA from GitHub.
 * @returns {Promise<string>} the 40-char HEAD SHA
 */
async function resolveHead() {
  const head = await agent(
    `Print the current HEAD SHA of ${prCoordinates}. Run exactly:\n` +
      `gh api repos/${args.owner}/${args.repo}/pulls/${args.prNumber} --jq .head.sha\n` +
      `Return the full 40-character SHA in the sha field. Do not modify any files.`,
    { label: 'resolve-head', phase: 'Converge', schema: HEAD_SCHEMA, agentType: 'Explore' },
  )
  return head?.sha
}

/**
 * Bugbot lens: ensure Cursor Bugbot has rendered a verdict on the given HEAD,
 * triggering and polling its CI check run when needed, and return its findings.
 * @param {string} head PR HEAD SHA to evaluate
 * @returns {Promise<object>} LENS_SCHEMA result
 */
function runBugbotLens(head) {
  if (args.bugbotDisabled) {
    return Promise.resolve({ sha: head, clean: true, down: true, findings: [] })
  }
  return agent(
    `You are the Cursor Bugbot lens for ${prCoordinates}, HEAD ${head}. ${bugbotDisabledNote}\n\n` +
      `Goal: return Bugbot's verdict on HEAD ${head}. Do not edit code, commit, or push. You may post the literal trigger comment described below.\n\n` +
      `Procedure (use the existing scripts; pass --owner ${args.owner} --repo ${args.repo}):\n` +
      `1. Opt-out: python "${CONFIG.prLoopScripts}/reviews_disabled.py" --reviewer bugbot. Exit 0 means disabled -> return {sha, clean:true, down:true, findings:[]}.\n` +
      `2. Silent pass: python "${CONFIG.sharedScripts}/check_bugbot_ci.py" --owner ${args.owner} --repo ${args.repo} --sha ${head} --check-clean. Exit 0 means the CI check completed clean with no review -> return clean with no findings.\n` +
      `3. Fetch any Bugbot review + inline comments on HEAD ${head} with gh api (Bugbot's GitHub login contains "cursor", case-insensitive). Use --paginate --slurp piped to external jq:\n` +
      `   gh api "repos/${args.owner}/${args.repo}/pulls/${args.prNumber}/reviews" --paginate --slurp  (top-level review body + state)\n` +
      `   gh api "repos/${args.owner}/${args.repo}/pulls/${args.prNumber}/comments" --paginate --slurp  (inline review comments + their ids)\n` +
      `   Only count entries whose commit_id starts with ${head}.\n` +
      `   - If findings exist on HEAD -> return them (each with its inline comment id in replyToCommentId when present, else null).\n` +
      `   - If a clean review exists on HEAD -> return clean.\n` +
      `4. No review yet on HEAD: check_bugbot_ci.py --check-active. If active (exit 0), poll: repeat check_bugbot_ci.py --check-clean / --check-active every 60 seconds (use a single PowerShell loop with Start-Sleep -Seconds 60) for up to 25 iterations, then re-fetch the review. If not active (exit 1), post the literal comment "bugbot run" (no @mention, no other text) via python "${CONFIG.sharedScripts}/post_fix_reply.py" --owner ${args.owner} --repo ${args.repo} --pr-number ${args.prNumber} --body "bugbot run", wait 8 seconds, then poll as above.\n` +
      `5. If after the full poll budget Bugbot has neither a check run nor a review on HEAD -> return {sha:${'`'}${head}${'`'}, clean:true, down:true, findings:[]} (treat as down).\n\n` +
      `Scope is the whole PR; you are only reading Bugbot's own output here. Return strictly the schema.`,
    { label: 'lens:bugbot', phase: 'Converge', schema: LENS_SCHEMA },
  )
}

/**
 * Code-review lens: a full-diff /code-review-style pass that reports findings
 * without applying any fix.
 * @param {string} head PR HEAD SHA to evaluate
 * @returns {Promise<object>} LENS_SCHEMA result
 */
function runCodeReviewLens(head) {
  return agent(
    `You are the code-review lens for ${prCoordinates}, HEAD ${head}.\n\n` +
      `Review the FULL origin/main...HEAD diff — every file the PR touches. Do NOT delta-scope to recent commits or to a single file. First run: git fetch origin main; git diff --name-only origin/main...HEAD to enumerate the changed files, then review the complete diff of each.\n\n` +
      `Apply correctness-focused review: real bugs, broken logic, incorrect error handling, data-loss or security risks, contract mismatches, and reuse/simplification problems. Report only defensible findings with concrete file:line evidence.\n\n` +
      `Do NOT edit, commit, or push — reporting only. Return strictly the schema: clean=true with empty findings when the diff is sound, otherwise one entry per finding (severity P0/P1/P2, replyToCommentId=null since these are not yet GitHub threads). Set sha=${'`'}${head}${'`'}, down=false.`,
    { label: 'lens:code-review', phase: 'Converge', schema: LENS_SCHEMA, agentType: 'code-quality-agent' },
  )
}

/**
 * Bug-audit lens: the bugteam-class second-opinion audit over the full diff,
 * applying the shared A–P audit rubric. Reports findings without fixing.
 * @param {string} head PR HEAD SHA to evaluate
 * @returns {Promise<object>} LENS_SCHEMA result
 */
function runAuditLens(head) {
  return agent(
    `You are the second-opinion bug-audit lens for ${prCoordinates}, HEAD ${head}.\n\n` +
      `Read the audit rubric at ${CONFIG.bugteamRubric} and apply its categories (A through P) against the FULL origin/main...HEAD diff — every file the PR touches, never a delta cut. Run git fetch origin main; git diff --name-only origin/main...HEAD first to enumerate scope.\n\n` +
      `This is a clean-room audit: assume nothing from other lenses. Report only findings backed by concrete file:line evidence. Do NOT edit, commit, or push.\n\n` +
      `Return strictly the schema: clean=true with empty findings when the diff passes every category, otherwise one entry per finding (severity P0/P1/P2, replyToCommentId=null). Set sha=${'`'}${head}${'`'}, down=false.`,
    { label: 'lens:bug-audit', phase: 'Converge', schema: LENS_SCHEMA, agentType: 'code-quality-agent' },
  )
}

/**
 * Fix lens: one clean-coder applies every finding in a single TDD commit,
 * pushes, then replies to and resolves any real GitHub review threads.
 * @param {string} head PR HEAD SHA the findings were raised against
 * @param {Array<object>} findings deduped findings across all lenses
 * @param {string} sourceLabel short description of where the findings came from
 * @returns {Promise<object>} FIX_SCHEMA result
 */
function applyFixes(head, findings, sourceLabel) {
  const findingsBlock = findings
    .map((each, position) => {
      const eachThreadIds = collectFindingThreadIds(each)
      const threadNote = eachThreadIds.length
        ? `\n   (GitHub review comment ids: ${eachThreadIds.join(', ')})`
        : ''
      return `${position + 1}. [${each.severity}] ${each.file}:${each.line} — ${each.title}\n   ${each.detail}${threadNote}`
    })
    .join('\n')
  const threadIds = findings
    .flatMap((each) => collectFindingThreadIds(each))
    .filter((each) => typeof each === 'number')
  return agent(
    `You are fixing ${findings.length} finding(s) (${sourceLabel}) on ${prCoordinates}, HEAD ${head}.\n\n` +
      `Findings:\n${findingsBlock}\n\n` +
      `Rules:\n` +
      `- Confirm the working tree is on the PR branch at HEAD ${head} with no unrelated edits before you start.\n` +
      `- Fix every finding test-first (failing test, then minimum code to pass) per CODE_RULES. Verify each concern against current code; a finding whose concern no longer applies needs no code change but still needs its thread resolved.\n` +
      `- Make ONE commit for all fixes, then push to the PR branch.\n` +
      `- For each finding that carries a GitHub review comment id (${threadIds.length ? threadIds.join(', ') : 'none this batch'}): post an inline reply with python "${CONFIG.sharedScripts}/post_fix_reply.py" --owner ${args.owner} --repo ${args.repo} --pr-number ${args.prNumber} --in-reply-to <id> --body "<what changed>", then resolve that thread (use the github MCP pull_request_review_write method=resolve_thread, or gh api graphql resolveReviewThread).\n` +
      `- Findings with replyToCommentId null are in-memory audit findings: fix them, no reply needed.\n\n` +
      `Return the new HEAD SHA after your push in newSha, pushed=true, and a one-line summary.`,
    { label: `fix:${sourceLabel}`, phase: 'Converge', schema: FIX_SCHEMA, agentType: 'clean-coder' },
  )
}

/**
 * Post the terminal CLEAN bugteam audit artifact so check_convergence.py sees
 * a clean bugteam review on the converged HEAD.
 * @param {string} head converged PR HEAD SHA
 * @returns {Promise<string>} agent transcript (unused)
 */
function postCleanAudit(head) {
  return agent(
    `Post a CLEAN bugteam audit review on ${prCoordinates} at commit ${head}. All review lenses are clean on this HEAD.\n\n` +
      `Write an empty findings file: create a temp file containing exactly [] (an empty JSON array). Then run:\n` +
      `python "${CONFIG.prLoopScripts}/post_audit_thread.py" --skill bugteam --owner ${args.owner} --repo ${args.repo} --pr-number ${args.prNumber} --commit ${head} --state CLEAN --findings-json <temp-file>\n` +
      `Run the script with --help first if any flag name differs. This posts the APPROVE review body that check_convergence.py reads for the bugteam gate. Do not edit code, commit, or push.`,
    { label: 'post-clean-audit', phase: 'Converge', agentType: 'general-purpose' },
  )
}

/**
 * Copilot gate: request a Copilot review on HEAD and poll until it lands or the
 * poll cap is hit; return Copilot's findings or a blocker.
 * @param {string} head converged PR HEAD SHA
 * @returns {Promise<object>} COPILOT_SCHEMA result
 */
function runCopilotGate(head) {
  return agent(
    `You are the Copilot gate for ${prCoordinates}, HEAD ${head}. Do not edit code, commit, or push.\n\n` +
      `1. Skip a duplicate request: python "${CONFIG.sharedScripts}/check_pending_reviews.py" --owner ${args.owner} --repo ${args.repo} --pr-number ${args.prNumber} --user copilot. Exit 0 means a request is already pending; otherwise request one:\n` +
      `   gh api --method POST repos/${args.owner}/${args.repo}/pulls/${args.prNumber}/requested_reviewers -f 'reviewers[]=copilot-pull-request-reviewer[bot]'\n` +
      `2. Poll for Copilot's review on HEAD ${head}: up to ${CONFIG.copilotMaxPolls} attempts, 360 seconds apart (one PowerShell loop with Start-Sleep -Seconds 360). Each attempt: python "${CONFIG.sharedScripts}/fetch_copilot_reviews.py" --owner ${args.owner} --repo ${args.repo} --pr-number ${args.prNumber} for the top-level review state, plus gh api "repos/${args.owner}/${args.repo}/pulls/${args.prNumber}/comments" --paginate --slurp for inline comment ids (Copilot's login contains "copilot", case-insensitive). Only count entries whose commit_id starts with ${head}.\n` +
      `   - Copilot review present and clean/approved on HEAD -> return {sha:${'`'}${head}${'`'}, clean:true, findings:[], blocker:null}.\n` +
      `   - Copilot findings on HEAD -> return them (each with its inline comment id in replyToCommentId), clean:false, blocker:null.\n` +
      `   - No review after ${CONFIG.copilotMaxPolls} attempts -> return {sha:${'`'}${head}${'`'}, clean:false, findings:[], blocker:"Copilot did not surface a review on HEAD after ${CONFIG.copilotMaxPolls} polls"}.\n\n` +
      `Return strictly the schema.`,
    { label: 'copilot-gate', phase: 'Copilot gate', schema: COPILOT_SCHEMA },
  )
}

/**
 * Run the authoritative convergence gate.
 * @param {boolean} bugbotDown pass --bugbot-down when Bugbot is opted out or proved unreachable this run
 * @returns {Promise<object>} CONVERGENCE_SCHEMA result
 */
function checkConvergence(bugbotDown) {
  const bugbotDownFlag = bugbotDown ? ' --bugbot-down' : ''
  return agent(
    `Run the convergence gate for ${prCoordinates} and report the result. Do not edit code.\n\n` +
      `Run: python "${CONFIG.sharedScripts}/check_convergence.py" --owner ${args.owner} --repo ${args.repo} --pr-number ${args.prNumber}${bugbotDownFlag}\n\n` +
      `Exit 0 -> every gate passed: return {pass:true, failures:[]}.\n` +
      `Exit 1 -> return {pass:false, failures:[<each printed FAIL line verbatim>]}.\n` +
      `Exit 2 -> retry once; if it still errors, return {pass:false, failures:["check_convergence gh error"]}.`,
    { label: 'check-convergence', phase: 'Finalize', schema: CONVERGENCE_SCHEMA, agentType: 'Explore' },
  )
}

/**
 * Mark the PR ready for review (draft=false).
 * @param {string} head converged PR HEAD SHA
 * @returns {Promise<string>} agent transcript (unused)
 */
function markReady(head) {
  return agent(
    `All convergence gates pass for ${prCoordinates} on HEAD ${head}. Mark the PR ready: run\n` +
      `gh pr ready ${args.prNumber} --repo ${args.owner}/${args.repo}\n` +
      `Do not edit code.`,
    { label: 'mark-ready', phase: 'Finalize', agentType: 'general-purpose' },
  )
}

/**
 * Address the gates a convergence check reported as failing, then hand control
 * back to the converge phase. Resolves lingering bot threads and rebases when
 * the PR is not mergeable.
 * @param {string} head current PR HEAD SHA
 * @param {Array<string>} failures FAIL lines from the convergence check
 * @returns {Promise<object>} FIX_SCHEMA result
 */
function repairConvergence(head, failures) {
  const failureBlock = failures.length
    ? failures.map((each, position) => `${position + 1}. ${each}`).join('\n')
    : 'none reported'
  return agent(
    `The convergence check for ${prCoordinates} failed these gates on HEAD ${head}:\n${failureBlock}\n\n` +
      `Address only the failing gates:\n` +
      `- Unresolved bot review threads: fetch every thread where isResolved is false (gh api graphql, or the github MCP pull_request_read get_review_comments). For each, verify the concern against current code; if it still applies, fix it test-first; either way post an inline reply and resolve the thread.\n` +
      `- PR not mergeable: rebase onto origin/main and force-push (git fetch origin main; git rebase origin/main; resolve conflicts; git push --force-with-lease).\n` +
      `- A dirty bot review or a still-pending requested reviewer: leave it; the next round re-runs that reviewer.\n` +
      `Make at most one commit for any code fix. Return the HEAD SHA after any push in newSha (the unchanged ${head} when nothing was pushed), pushed true/false, and a one-line summary.`,
    { label: 'repair-convergence', phase: 'Finalize', schema: FIX_SCHEMA, agentType: 'clean-coder' },
  )
}

let phase = 'CONVERGE'
let head = null
let rounds = 0
let blocker = null
let bugbotDown = args.bugbotDisabled || false

while (rounds < CONFIG.maxRounds) {
  if (phase === 'CONVERGE') {
    rounds += 1
    head = await resolveHead()
    if (!isResolvedHeadUsable(head)) {
      log(`Round ${rounds}: resolve-head agent returned no SHA — retrying without spawning lenses`)
      continue
    }
    log(`Round ${rounds}: parallel Bugbot + code-review + bug-audit on ${head?.slice(0, 7)}`)
    const lenses = await parallel([
      () => runBugbotLens(head),
      () => runCodeReviewLens(head),
      () => runAuditLens(head),
    ])
    bugbotDown = resolveBugbotDown(lenses[0], args.bugbotDisabled || false)
    const roundOutcome = resolveRoundOutcome(lenses)
    if (roundOutcome.allLensesDead) {
      log(`Round ${rounds}: every lens agent died — retrying without posting a clean artifact`)
      continue
    }
    const findings = roundOutcome.findings
    if (findings.length > 0) {
      log(`Round ${rounds}: ${findings.length} finding(s) — applying fixes`)
      const fixResult = await applyFixes(head, findings, 'converge-round')
      const fixProgress = detectFixProgress(fixResult, head)
      if (!fixProgress.progressed) {
        blocker = `fix lens landed no push for ${findings.length} finding(s) on HEAD ${head}`
        break
      }
      head = fixProgress.newSha
      continue
    }
    log(`Round ${rounds}: all lenses clean on ${head?.slice(0, 7)} — posting clean audit artifact`)
    await postCleanAudit(head)
    phase = 'COPILOT'
    continue
  }

  if (phase === 'COPILOT') {
    const copilot = await runCopilotGate(head)
    const copilotOutcome = classifyCopilotOutcome(copilot)
    if (copilotOutcome.kind === 'retry') {
      log('Copilot gate agent died — re-running the gate on the same HEAD')
      continue
    }
    if (copilotOutcome.kind === 'blocker') {
      blocker = copilotOutcome.blocker
      break
    }
    if (copilotOutcome.kind === 'fix') {
      log(`Copilot raised ${copilotOutcome.findings.length} finding(s) — fixing and re-converging`)
      const fixResult = await applyFixes(head, copilotOutcome.findings, 'copilot')
      const fixProgress = detectFixProgress(fixResult, head)
      if (!fixProgress.progressed) {
        blocker = `copilot fix lens landed no push for ${copilotOutcome.findings.length} finding(s) on HEAD ${head}`
        break
      }
      head = fixProgress.newSha
      phase = 'CONVERGE'
      continue
    }
    phase = 'FINALIZE'
    continue
  }

  if (phase === 'FINALIZE') {
    const convergence = await checkConvergence(bugbotDown)
    if (convergence?.pass) {
      await markReady(head)
      return { converged: true, rounds, finalSha: head, blocker: null }
    }
    log(`Convergence check failed: ${(convergence?.failures || []).join('; ') || 'unknown'} — repairing then re-converging`)
    const repair = await repairConvergence(head, convergence?.failures || [])
    head = repair?.newSha || head
    phase = 'CONVERGE'
    continue
  }
}

return {
  converged: false,
  rounds,
  finalSha: head,
  blocker: blocker || `round cap reached (${CONFIG.maxRounds})`,
}
