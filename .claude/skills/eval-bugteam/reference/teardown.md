# Teardown

## Step 4 Checklist

1. **Worktree removal.** `git worktree remove "<run_temp_dir>/pr-<N>/worktree"`
   for each PR. Tolerate already-removed worktrees.

2. **Windows-safe temp directory removal.** Use the `force_rmtree` pattern
   to strip ReadOnly attributes before deleting:

   ```python
   import os, shutil, stat, sys
   def _strip_and_retry(f, p, *e):
       try:
           os.chmod(p, stat.S_IWRITE)
           f(p)
       except OSError:
           pass
   handler_kw = (
       {"onexc": _strip_and_retry} if sys.version_info >= (3, 12)
       else {"onerror": _strip_and_retry}
   )
   shutil.rmtree("<run_temp_dir>", **handler_kw)
   ```

3. **Permission revocation.** Run `revoke_project_claude_permissions.py`
   on every exit path (Step 5), even if Step 4 partially failed.

4. **PR description update.** (Step 4.5) Rewrite PR body if the diff is
   merge-ready.
