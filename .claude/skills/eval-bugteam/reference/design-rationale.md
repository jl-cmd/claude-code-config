# Design Rationale

## Why Single Opus (Not 10 Haiku + Validator)

Earlier versions used a phased parallel model: 10 haiku auditors → wait →
1 opus validator. This was reverted because:

- **Cost.** 10 haiku + 1 opus costs more than 1 opus alone while
  producing lower-quality findings that the validator then needs to fix.
- **Hallucination amplification.** Haiku auditors produce more
  false-positive findings, which the validator must catch and quarantine.
  Each rejected finding wastes the haiku's context budget and the
  validator's review budget.
- **Orchestration complexity.** Ten background agents require waiting,
  timeout handling, diagnostics, and dedup logic that a single agent
  avoids entirely.

## Why Fresh Spawn Per Loop

- **Bias isolation.** Prior loop findings should not influence the next
  audit. Each loop starts from first principles.
- **No hallucination amplification.** An agent that hallucinated a
  finding in loop N should not carry that hallucination into loop N+1.
- **Clean context.** Each loop's agent gets only the PR scope, not the
  entire loop history.

## Why Background Execution

The `run_in_background=true` pattern keeps the lead responsive:
- Lead can handle timeouts without blocking
- Lead can process multiple PRs in parallel
- Background agent failures don't crash the lead
