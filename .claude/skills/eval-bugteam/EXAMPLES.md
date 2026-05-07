# Exit Scenarios

## converged

Back-to-back clean reviews on the same HEAD. Bugbot clean, eval-bugteam
clean, and (in ROUND 2) Copilot clean all on the same commit SHA. The PR
then proceeds through convergence gates.

## cap reached

10 audit-fix loops exhausted without reaching convergence. Suggests the
PR has structural issues the audit rubric cannot address, or the FIX
agents are introducing new findings faster than they resolve them.

**Next step:** Run `/findbugs` for a fresh perspective, or manually
review the remaining findings.

## stuck

The FIX subagent exited without producing any new commits. This happens
when all findings were hook_blocked or could_not_address. No progress
was made this loop.

**Next step:** Review the hook_blocked reasons. If the findings are
predominantly P2/style, consider P2-only early convergence.

## error

Pre-flight failed and could not be auto-remediated, or the code rules
gate blocked the audit 5+ times in a row.

**Next step:** Fix the preflight/gate issue manually, then re-invoke.
