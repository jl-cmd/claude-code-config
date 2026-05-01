# gh API Pagination Rule

**Root cause:** The GitHub REST API returns 30 items per page by default. `gh api repos/<owner>/<repo>/pulls/<number>/reviews` and `gh api repos/<owner>/<repo>/pulls/<number>/comments` silently truncate at 30 results without warning. PRs that have accumulated more than 30 reviews or inline comments — common on long PR-loop cycles where bugbot, copilot, or the in-house bugteam each post repeatedly — return only the **oldest** 30, hiding the most recent reviews and findings entirely. A `sort_by(.submitted_at) | last` (or `| reverse`) on a truncated array picks the latest entry **within the first 30**, not the actual latest, which produces a stale-but-confident report that then drives wrong decisions (e.g., re-triggering bugbot when it has already posted a CLEAN review on a later page).

**Rule:** All `gh api` calls that read `pulls/<number>/reviews`, `pulls/<number>/comments`, `issues/<number>/comments`, or any other paginated GitHub list endpoint **must** request the full set of pages. Use `--paginate` (preferred) or `?per_page=100` (when paginate is not desired and you have verified the result fits in one page). Never call these endpoints with their default pagination.

## Affected endpoints

The rule applies to every paginated read from the GitHub REST API. Common offenders in this repo's PR-loop skills:

- `gh api repos/<owner>/<repo>/pulls/<number>/reviews`
- `gh api repos/<owner>/<repo>/pulls/<number>/comments`
- `gh api repos/<owner>/<repo>/pulls/<number>/files`
- `gh api repos/<owner>/<repo>/issues/<number>/comments`
- `gh api repos/<owner>/<repo>/pulls`
- `gh api repos/<owner>/<repo>/issues`

The same rule applies to any other endpoint documented as paginated by GitHub (see [GitHub REST API pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)).

## Safe patterns

### Preferred — `--paginate` flag

`gh` walks every page automatically and concatenates the JSON arrays before `--jq` runs:

```bash
gh api 'repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100' --paginate \
  --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | last'
```

Combine `--paginate` with `?per_page=100` so each page fetches 100 items instead of 30, reducing round-trips on long PRs without changing correctness.

### Acceptable — single-page bound when result fits

When you have an explicit reason to read at most one page (e.g., a known-small endpoint), document the bound in a comment and use `?per_page=100`:

```bash
gh api 'repos/<owner>/<repo>/pulls/<number>?per_page=100' \
  --jq '.head.sha'
```

This pattern is only safe when the endpoint is confirmed to return a single object or a list smaller than 100 entries. Lists that grow over the PR's lifetime (reviews, comments) must use `--paginate`.

### Newest-first walk

Pair pagination with explicit reverse-sort so the consumer reads newest-first regardless of the API's internal order:

```bash
gh api 'repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100' --paginate \
  --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | reverse'
```

This is the canonical pattern for the bugbot ↔ bugteam convergence loop: walk newest-first, stop at the first clean review.

## What NOT to do

```bash
# BAD — default 30-item page silently truncates on long PRs
gh api repos/<owner>/<repo>/pulls/<number>/reviews \
  --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | last'

# BAD — `?per_page=100` alone caps at 100 items; PRs with 100+ reviews still truncate
gh api 'repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100' \
  --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | last'

# BAD — taking `| last` on an unpaginated read returns the latest of the first 30,
# not the actual latest. Same defect for `| reverse | .[0]`.
```

## Why a `last` on truncated input lies

`gh api`'s default page is the FIRST page of results, ordered oldest-to-newest by the GitHub API. When the result set exceeds 30 items, page 1 contains the OLDEST 30 — not the newest. A jq `| last` after `sort_by(.submitted_at)` picks the latest entry within those 30 oldest items, producing output that looks correct but reports a state from days or weeks ago. The skill that consumes this output then makes decisions (re-trigger bugbot, mark a finding stale, report convergence) against an obsolete view of the PR.

`--paginate` fixes this by walking all pages before jq runs, so `| last` operates on the full set.

## Consumers

Skills and scripts in this repo that read paginated endpoints and must therefore use `--paginate`:

- `pr-converge` — bugbot review walk (BUGBOT phase, Step 2.a) and inline-comments fetch (Step 2.b).
- `bugteam` — review threads, inline comments, audit-loop history.
- `qbug` — same as bugteam, scoped to a single subagent loop.
- `pr-review-responder` — review comments fetch (already enforced; this rule extends the same constraint to reviews and other endpoints).
- `monitor-many` — open-PR enumeration and per-PR review/comment scans.
- `babysit-pr` — review-comment polling.

Updating any of these to read paginated endpoints requires `--paginate` or a documented single-page bound.

## Enforcement

This rule is documentation-only at present. A future PreToolUse hook may pattern-match `Bash` invocations of `gh api repos/.../pulls/<n>/(reviews|comments)` without `--paginate` and `?per_page=` and return a corrective message. Until that hook lands, treat this rule as binding by review and rely on it during skill authoring.

## Precedent

The `pr-review-responder` skill predated this rule and forbids default pagination on `pulls/<n>/comments` reads (`packages/claude-dev-env/skills/pr-review-responder/SKILL.md` Rule 1). This file generalizes that constraint to every paginated GitHub endpoint and centralizes the safe patterns so additional skills inherit the rule by reference instead of restating it.
