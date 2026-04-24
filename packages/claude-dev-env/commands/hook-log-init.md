---
description: Initialize the Neon schema used by the hook-log extractor
allowed-tools: Bash
---

Initialize the Neon Postgres schema that backs the hook-log diagnostic
extractor. Run this once per new machine, or after rotating the Neon
project, before the Stop hook begins inserting rows.

## Prerequisites

One-time setup on each machine:

1. **Install the Bitwarden Secret Manager CLI** so the `bws` command is on PATH.
   See https://bitwarden.com/help/secrets-manager-cli/ for platform-specific instructions.

2. **Create a Bitwarden machine account** scoped to the Neon connection
   secret, generate its access token, and export it to the current user
   environment on Windows:

   ```powershell
   setx BWS_ACCESS_TOKEN "<machine-account-access-token>"
   ```

   Open a new terminal so the variable takes effect.

3. **Store the Neon connection string** in the Bitwarden Secrets Manager
   under the key `NEON_HOOK_LOGS_DATABASE_URL`. The value is the full
   `postgres://user:password@host/database?sslmode=require` URL that
   Neon provides on the project dashboard.

4. **Install the Python dependencies** so the extractor can reach Neon:

   ```
   pip install -r packages/claude-dev-env/hooks/diagnostic/requirements-hook-logs.txt
   ```

## Run the init

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_init.py
```

The init script performs these steps in order:

1. Verifies `NEON_HOOK_LOGS_DATABASE_URL` and `BWS_ACCESS_TOKEN` are set.
2. Connects to Neon with a 5-second timeout.
3. Applies the DDL in `packages/claude-dev-env/hooks/diagnostic/schema.sql`
   using `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and
   `CREATE OR REPLACE VIEW` so the script stays idempotent.
4. Inserts a sentinel row with `outcome = 'init_probe'`, selects it back,
   and deletes it to confirm read-write parity.
5. Prints a success report showing the Neon host, table name, and row count.

A missing environment variable exits with status 1 and lists the
missing name on stderr; any other failure surfaces the psycopg exception.
