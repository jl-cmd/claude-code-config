# Scripts

| Script | Purpose | Parameters |
|--------|---------|------------|
| `view_pr_context.py` | Resolve current PR HEAD, owner, repo, branch from PR number | `--owner`, `--repo`, `--number` |
| `fetch_bugbot_reviews.py` | Fetch Cursor Bugbot reviews, classify as clean/dirty | `--owner`, `--repo`, `--number` |
| `fetch_bugbot_inline_comments.py` | Fetch inline comments for latest bugbot review on HEAD | `--owner`, `--repo`, `--number`, `--commit` |
| `resolve_pr_head.py` | Re-resolve PR HEAD (after eval-bugteam push) | `--owner`, `--repo`, `--number` |
| `trigger_bugbot.py` | Post "bugbot run" comment to re-trigger Cursor Bugbot | `--owner`, `--repo`, `--number` |
