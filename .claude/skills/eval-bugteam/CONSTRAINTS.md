# Constraints

Design invariants and hard rules for the bugteam skill.

1. **Clean-room audit isolation.** Each loop spawns a fresh subagent with
   zero conversation context from prior loops. No state is carried between
   audit invocations.

2. **Code is assumed correct unless proven otherwise.** The audit does not
   assume defects exist. Every category requires evidence of a concrete bug
   before filing a finding.

3. **No AI-generated fix suggestions.** Findings must cite specific file:line
   evidence. AI-generated "maybe fix by..." without evidence is not a finding.

4. **Per-loop PR reviews, not issue comments.** Each audit loop posts one
   review via the 3-step GH API. Issue comments are fallback only when the
   review POST fails.

5. **10-loop hard cap.** After 10 audit-fix cycles, the loop exits with
   `cap reached`. No loop may exceed this limit.

6. **Scope limited to PR diff only.** Pre-existing code on untouched lines
   is out of scope. Only lines added or modified in the diff are audited.
