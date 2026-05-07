# GitHub API Payloads

## Review POST (3-Step)

All bugteam audit reviews use this three-step flow via MCP tool calls.

### Step 1 — Create Pending Review

```
pull_request_review_write(
  method="create",
  commitID=<head_sha>,
  owner=<owner>,
  repo=<repo>,
  pullNumber=<number>
)
```

### Step 2 — Add Inline Comments

```
add_comment_to_pending_review(
  path=<file_path>,
  line=<line>,
  side="RIGHT",
  body=<finding_body>,
  owner=...,
  repo=...,
  pullNumber=...,
)
```

For multi-line findings, also pass `start_line` and `start_side="RIGHT"`.

### Step 3 — Submit Pending Review

```
pull_request_review_write(
  method="submit_pending",
  event="COMMENT",
  body=<review_body_text>,
  owner=...,
  repo=...,
  pullNumber=...,
)
```

## Fix Reply

```
add_reply_to_pull_request_comment(
  commentId=<finding_comment_id>,
  body=<reply_text>,
  owner=...,
  repo=...,
  pullNumber=...,
)
```

## Issue Comment Fallback

When review POST fails:

```
add_issue_comment(
  owner=...,
  repo=...,
  issue_number=<number>,
  body=<fallback_text>,
)
```

## Parameter Patterns

| Operation | Tool | Key Fields |
|-----------|------|------------|
| Create pending review | `pull_request_review_write` | method=create, commitID, owner, repo, pullNumber |
| Add inline comment | `add_comment_to_pending_review` | path, line, side, body, owner, repo, pullNumber |
| Submit pending review | `pull_request_review_write` | method=submit_pending, event, body |
| Post fix reply | `add_reply_to_pull_request_comment` | commentId, body |
| Issue comment fallback | `add_issue_comment` | issue_number, body |
