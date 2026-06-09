/**
 * Pure convergence-loop decision functions, kept in an importable module so they
 * can be unit-tested without executing the workflow driver in converge.mjs.
 */

/**
 * Classify a Copilot gate result into the loop's next action. A dead gate agent
 * (null result) is a retry rather than an approval, mirroring the converge
 * lenses' dead-agent convention so a failed gate is never mistaken for a clean
 * Copilot review. A non-null blocker ends the run; findings route to a fix step.
 * The gate approves only when it explicitly reports clean:true with no findings —
 * a clean:false result with zero findings is an unreliable or malformed gate
 * response and retries rather than advancing to Finalize, so a PR never goes
 * ready on a HEAD Copilot did not call clean.
 * @param {object|null|undefined} copilot the Copilot gate result, or null on agent failure
 * @returns {{kind: string, blocker?: string, findings?: Array<object>}} the next action
 */
export function classifyCopilotOutcome(copilot) {
  if (copilot == null) return { kind: 'retry' }
  if (copilot.blocker) return { kind: 'blocker', blocker: copilot.blocker }
  if (copilot.findings.length > 0) return { kind: 'fix', findings: copilot.findings }
  if (copilot.clean === true) return { kind: 'approved' }
  return { kind: 'retry' }
}

/**
 * Classify a convergence-check result into the loop's next action. A dead check
 * agent (null/undefined result) is a retry rather than a failure: with no FAIL
 * lines to act on, running the convergence repair (which may rebase and
 * force-push) would be a destructive response to a transient agent death. A
 * genuine pass marks the PR ready; a real failure carrying FAIL lines routes to
 * repair; a pass:false report with no failure lines is an unreliable check and
 * retries rather than triggering a repair with nothing concrete to fix.
 * @param {object|null|undefined} convergence the convergence-check result, or null on agent failure
 * @returns {{kind: string, failures?: Array<string>}} the next action
 */
export function classifyConvergenceOutcome(convergence) {
  if (convergence == null) return { kind: 'retry' }
  if (convergence.pass === true) return { kind: 'ready' }
  const failures = convergence.failures || []
  if (failures.length === 0) return { kind: 'retry' }
  return { kind: 'repair', failures }
}
