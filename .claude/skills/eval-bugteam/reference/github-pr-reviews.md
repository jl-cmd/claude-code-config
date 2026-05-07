# GitHub PR Reviews

## Lifecycle

Each audit loop posts exactly one review. The review lifecycle is:

1. **Create pending review** — reserves a review slot
2. **Add inline comments** — one per anchored finding
3. **Submit pending review** — posts the review with body

## MCP Tool Calls

All review operations use MCP tool calls exclusively. No shell commands,
no temp files, no jq pipes. Body text with markdown (backticks, newlines,
quotes) passes through safely as string parameters.

## Endpoints

| Operation | Tool |
|-----------|------|
| Create pending review | `pull_request_review_write(method="create", ...)` |
| Add inline comment | `add_comment_to_pending_review(...)` |
| Submit pending | `pull_request_review_write(method="submit_pending", ...)` |
| Post fix reply | `add_reply_to_pull_request_comment(...)` |
| Issue fallback | `add_issue_comment(...)` |

## Review Body Template

```
## /eval-bugteam round <R> loop <L> audit: <P0>P0 / <P1>P1 / <P2>P2

### Findings without a diff anchor
(only if needed)
- **[severity] title** — <file>:<line> — <one-line>
```

## Fallback

When review POST fails, post one issue comment with all findings. All
findings get `used_fallback="true"` and the issue comment URL replaces
the review URL.
