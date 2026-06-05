---
name: secure-share
description: >-
  Shares a local file with one or more named recipients via Google Drive
  with restricted per-email access. Never link-shareable. HTML inputs are
  rendered to PDF via Chrome headless so Drive's web viewer shows them
  inline rather than prompting a download. Triggers on `/secure-share`,
  "share this privately with [name]", "publish for [named recipients]",
  "secure share this report", or any request to share a sensitive doc
  that must NOT be link-public. Skill type 4 (Business Process Automation).
---

# secure-share

Share a file via Google Drive with a restricted viewer list. Pass `--email someone@example.com` to grant viewer access (repeat the flag for multiple recipients). With no `--email` flag, the file uploads private to the owner.

## When this applies

Trigger for requests that produce a sensitive doc (a writeup, report, plan, financial model) and ask to share it privately. The skill is the right answer when the link must be locked to specific Google accounts, never public.

**Refusal cases — first match wins:**

- **The artifact must reach someone without a Google account.** Respond exactly: `secure-share requires every viewer to have a Google account. Use a password-protected PDF over email instead.`
- **The artifact should be public or link-shareable.** Respond exactly: `secure-share locks viewers by email. For link-shareable rendering, use the doc-gist skill instead.`

## What it does

1. Accepts a local file path (HTML, PDF, markdown, image — anything Drive accepts).
2. If the input is HTML, renders it to PDF via Chrome headless. Drive's web viewer shows PDFs inline; raw HTML downloads instead.
3. Reuses a saved OAuth token at `${CLAUDE_PLUGIN_DATA}/secure-share/drive_token.json` (falls back to `~/.claude/state/secure-share/drive_token.json` when the env var is unset). First run opens Chrome for sign-in; later runs are silent.
4. Uploads to Drive against quota project `ynab-amazon-sync`.
5. Grants per-email Viewer access to each email passed via `--email`.
6. Prints the `https://drive.google.com/file/d/<id>/view` URL on stdout. Works in any browser, renders the artifact inline.

## Execute the script

```
python "<repo>/packages/claude-dev-env/skills/secure-share/scripts/publish.py" \
  --input "C:/path/to/file.html" \
  [--email someone@example.com] [--email second@example.com] \
  [--title "Custom Title for Drive listing"]
```

Sample output:

```
INFO Rendered HTML to PDF: C:\Users\jon\Documents\example-report.pdf
INFO Reusing saved token at C:\Users\jon\.claude\state\secure-share\drive_token.json
INFO Shared with alice@example.com as reader
INFO Drive view link: https://drive.google.com/file/d/<file-id>/view
https://drive.google.com/file/d/<file-id>/view
```

Quote the printed URL back to the user when invoking the script.

## Defaults

| Setting | Default | Why |
|---|---|---|
| Viewer role | `reader` | View + download; no edit |
| Notification email | off | Owner delivers the link |
| Quota project | `ynab-amazon-sync` | Drive API on; owner has `serviceusage.serviceUsageConsumer` |
| Token path | `${CLAUDE_PLUGIN_DATA}/secure-share/drive_token.json` | Survives skill upgrades |
| HTML → PDF | Chrome headless | Reuses installed Chrome |

## First-run authorization

The first invocation runs an OAuth flow:

1. Chrome opens to `accounts.google.com/o/oauth2/auth` with `drive.file` + `cloud-platform` scopes.
2. Sign in with the account that owns the Drive folder where uploads should land.
3. Approve both scopes (Drive write + cloud-platform for quota project usage).
4. Browser redirects to `http://localhost:8765/` and a local WSGI handler captures the code.
5. Token is saved; OAuth window can be closed.

## Dependencies

The script imports these third-party packages. Install via `pip install google-api-python-client google-auth-oauthlib`:

- `google-api-python-client` — Drive v3 client + `MediaFileUpload` for resumable uploads.
- `google-auth-oauthlib` — Installed-app OAuth flow + WSGI redirect handler.
- `google-auth` — Credentials objects (pulled in transitively).

Chrome must be installed for HTML → PDF conversion. The script searches Windows, macOS, and Linux default paths and falls back to the `webbrowser` module for opening the OAuth URL.

## Gotchas

- **Required IAM role on the quota project.** The signed-in account needs `roles/serviceusage.serviceUsageConsumer` on `ynab-amazon-sync`. Grant via `gcloud projects add-iam-policy-binding ynab-amazon-sync --member=user:<email> --role=roles/serviceusage.serviceUsageConsumer --condition=None` from a terminal where gcloud is signed in as a project owner. Propagation takes a couple of minutes.
- **HTML in Drive doesn't show as a webpage.** Drive renders raw HTML as a download preview. The script converts HTML → PDF on the way in. Pass `.pdf` directly to skip conversion.
- **OAuth client_secret is gcloud's public installed-app client.** The `OAUTH_CLIENT_SECRET` in `packages/claude-dev-env/skills/secure-share/scripts/config/secure_share_constants.py` is the publicly known secret for client `764086051850-...`. Per OAuth 2.0 for Installed Apps, installed-client secrets are not real secrets; security comes from the user consent screen, not the secret. Do not treat this as a credential leak.
- **Token scope mismatch forces re-auth.** Changing the `ALL_OAUTH_SCOPES` list invalidates the saved token — the script detects the mismatch and re-runs the flow.
- **Drive API must be enabled on the quota project.** First-time setup requires `gcloud services enable drive.googleapis.com --project=ynab-amazon-sync`. Later runs reuse the enablement.
- **Chrome path is host-specific.** The `ALL_CHROME_PATH_CANDIDATES` list in `packages/claude-dev-env/skills/secure-share/scripts/config/secure_share_constants.py` covers Windows (`Program Files\Google\Chrome\Application\chrome.exe`), macOS (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`), and Linux (`/usr/bin/google-chrome`, `/usr/bin/chromium-browser`). Add custom paths there for non-standard installs.
- **No link-shareable mode.** The skill never exposes `Anyone with the link` access by design. If link-shareable is wanted, use the `doc-gist` skill (renders as webpage, but anyone with the URL can read).
- **Port 8765 must be free for the OAuth callback.** The local WSGI server binds `localhost:8765` during the first-run flow. Conflict with another listener fails the auth. Stop the conflicting process or update `CALLBACK_PORT` in `packages/claude-dev-env/skills/secure-share/scripts/config/secure_share_constants.py` and re-run.

## When NOT to use

- The artifact is meant to be public or indexed → use `doc-gist`.
- The artifact must stay local-only → don't upload at all.
- The recipient does not have a Google account → password-protected PDF over email.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This hub — when-this-applies, defaults, dependencies, gotchas, file index. |
| `packages/claude-dev-env/skills/secure-share/scripts/publish.py` | The upload script. CLI entry point + `publish()` function. |
| `packages/claude-dev-env/skills/secure-share/scripts/config/secure_share_constants.py` | Scalar constants (OAuth scopes, Drive field keys, Chrome paths). |
| `packages/claude-dev-env/skills/secure-share/scripts/config/__init__.py` | Package marker for the config subpackage. |
| `packages/claude-dev-env/skills/secure-share/scripts/test_publish.py` | Behavior tests for `_merge_recipients`, `_is_html_input`, and `_resolve_token_path`. |

## Folder map

- `SKILL.md` — hub.
- `scripts/` — executable Python entry point and tests.
- `scripts/config/` — scalar constants exempt from the file-global-constants use-count rule.
