#!/usr/bin/env python3
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.convergence_branch_constants import (  # noqa: E402
    ALL_CONVERGENCE_BRANCH_PREFIXES,
    CONVERGENCE_BRANCH_SUFFIX_PATTERN,
    CONVERGENCE_FORCE_PUSH_DETECTION_PATTERN,
)
from hooks_constants.destructive_command_segment_constants import (  # noqa: E402
    ALL_INTERPRETER_AND_WRAPPER_COMMANDS,
    ALL_REMOTE_AND_PROGRAM_STRING_EXECUTORS,
    ALL_SHELL_CONTROL_OPERATOR_TOKENS,
    ALL_STRING_ARGUMENT_EXECUTION_FLAGS,
)

CLAUDE_DIRECTORY_PATH = os.path.normpath(os.path.expanduser("~/.claude"))
GH_REDIRECT_ACTIVE_ENV_VAR = "CLAUDE_GH_REDIRECT_ACTIVE"
GH_REDIRECT_ACTIVE_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


def gh_redirect_is_active() -> bool:
    env_var_value = os.environ.get(GH_REDIRECT_ACTIVE_ENV_VAR, "").strip().lower()
    return env_var_value in GH_REDIRECT_ACTIVE_TRUTHY_VALUES

def directory_is_ephemeral(directory_path: str) -> bool:
    ephemeral_auto_allow_disabled_env_var = "CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW"
    truthy_string_values = frozenset({"1", "true", "yes", "on"})
    if os.environ.get(ephemeral_auto_allow_disabled_env_var, "").strip().lower() in truthy_string_values:
        return False
    forward_slash_normalized_directory_path = os.path.normpath(directory_path).replace("\\", "/").lower()
    all_ephemeral_path_segments = ("/worktrees/", "/worktree/", "/tmp/", "/temp/")
    for each_segment in all_ephemeral_path_segments:
        if each_segment in forward_slash_normalized_directory_path + "/":
            return True
    system_temporary_root = os.path.normpath(tempfile.gettempdir()).replace("\\", "/").lower()
    if forward_slash_normalized_directory_path.startswith(system_temporary_root + "/") or forward_slash_normalized_directory_path == system_temporary_root:
        return True
    try:
        git_rev_parse_completion = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=directory_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if git_rev_parse_completion.returncode != 0:
        return False
    git_directory_path_normalized = git_rev_parse_completion.stdout.strip().replace("\\", "/").lower()
    return "/.git/worktrees/" in git_directory_path_normalized or "/worktrees/" in git_directory_path_normalized


def load_allow_git_reset_hard_projects() -> list[str]:
    allow_git_reset_hard_settings_key = "allowGitResetHardProjects"
    settings_path = Path(CLAUDE_DIRECTORY_PATH) / "settings.json"
    try:
        raw_settings_text = settings_path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        parsed_settings = json.loads(raw_settings_text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed_settings, dict):
        return []
    hooks_section = parsed_settings.get("hooks")
    if not isinstance(hooks_section, dict):
        return []
    raw_allow_list = hooks_section.get(allow_git_reset_hard_settings_key)
    if not isinstance(raw_allow_list, list):
        return []
    return [
        each_project_path
        for each_project_path in raw_allow_list
        if isinstance(each_project_path, str)
    ]

DESTRUCTIVE_BASH_PATTERNS = [
    (re.compile(r'\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r', re.IGNORECASE), "rm -rf (destructive recursive forced delete)"),
    (re.compile(r'\brm\s+--recursive\b.*--force\b|\brm\s+--force\b.*--recursive\b', re.IGNORECASE), "rm --recursive --force (destructive recursive forced delete)"),
    (re.compile(r'\brm\s+-r\s+([/~]|\.(?:\s|$)|\$HOME)', re.IGNORECASE), "rm -r on broad path (/, ~, $HOME, .)"),
    (re.compile(r'\bmkfs\b', re.IGNORECASE), "mkfs (format filesystem)"),
    (re.compile(r'\bdd\s+.*\bif=.*\bof=/dev/', re.IGNORECASE), "dd raw disk write"),
    (re.compile(r'\bgit\s+reset\s+--hard\b', re.IGNORECASE), "git reset --hard (discards uncommitted work)"),
    (re.compile(r'\bgit\s+push\s+--force(?!-with-lease)\b', re.IGNORECASE), "git push --force (rewrites remote history)"),
    (re.compile(r'\bgit\s+push\s+-f\b', re.IGNORECASE), "git push -f (rewrites remote history)"),
    (re.compile(r'\bgit\s+clean\s+(-fd|-df)\b', re.IGNORECASE), "git clean -fd (deletes untracked files and dirs)"),
    (re.compile(r'\bgit\s+clean\s+-f\b', re.IGNORECASE), "git clean -f (deletes untracked files)"),
    (re.compile(r'\bDROP\s+TABLE\b', re.IGNORECASE), "DROP TABLE (destroys database table)"),
    (re.compile(r'\bDROP\s+DATABASE\b', re.IGNORECASE), "DROP DATABASE (destroys entire database)"),
    (re.compile(r'\bTRUNCATE\s+TABLE\b', re.IGNORECASE), "TRUNCATE TABLE (removes all table rows)"),
    (re.compile(r'\bgit\s+(?:[^\s]+\s+)*--no-verify\b', re.IGNORECASE), "git --no-verify (skips pre-commit / pre-push hooks; NON-NEGOTIABLE per git-workflow.md)"),
    (re.compile(r'\bgit\s+(?:[^\s]+\s+)*--no-gpg-sign\b', re.IGNORECASE), "git --no-gpg-sign (bypasses commit signing; NON-NEGOTIABLE per git-workflow.md)"),
    (re.compile(r"\bgit\s+-c\s+['\"]?commit\.gpgsign=['\"]?false['\"]?(?!\w)", re.IGNORECASE), "git -c commit.gpgsign=false (bypasses commit signing; NON-NEGOTIABLE per git-workflow.md)"),
]

def find_destructive_pattern(command: str) -> str | None:
    for pattern_regex, pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if pattern_regex.search(command):
            return pattern_description
    return None


def find_redirected_gh_pattern(command: str) -> str | None:
    redirected_gh_bash_patterns = [
        (re.compile(r'\bgh\s+api\b.*/(comments|reviews)\b.*-X\s+POST', re.IGNORECASE), "gh api comment/review POST"),
        (re.compile(r'\bgh\s+pr\s+comment\b', re.IGNORECASE), "gh pr comment"),
        (re.compile(r'\bgh\s+pr\s+review\b', re.IGNORECASE), "gh pr review"),
        (re.compile(r'\bgh\s+issue\s+comment\b', re.IGNORECASE), "gh issue comment"),
    ]
    for pattern_regex, pattern_description in redirected_gh_bash_patterns:
        if pattern_regex.search(command):
            return pattern_description
    return None


def _append_destructive_gate_log_entry(brief_label: str, full_reason: str) -> None:
    destructive_gate_log_path = Path.home() / ".claude" / "logs" / "destructive-gate.log"
    try:
        destructive_gate_log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp_iso = datetime.datetime.now().isoformat()
        log_entry = f"{timestamp_iso}\t{brief_label}\t{full_reason}\n"
        with destructive_gate_log_path.open("a", encoding="utf-8") as log_handle:
            log_handle.write(log_entry)
    except OSError:
        pass


def _build_silent_gh_deny_response(matched_description: str) -> dict:
    gh_gate_user_facing_prefix = "[gh-gate]"
    brief_label = f"blocked redirected {matched_description}"
    full_reason = (
        f"GH-REDIRECT GATE: {matched_description} already executed by "
        "gh-wsl-to-windows-redirect.py via PowerShell. Denying the original "
        "Bash call prevents duplicate execution."
    )
    _append_destructive_gate_log_entry(brief_label, full_reason)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": full_reason,
        },
        "suppressOutput": True,
        "systemMessage": f"{gh_gate_user_facing_prefix} {brief_label}",
    }


def _path_is_bare_ephemeral_root(resolved_path: str) -> bool:
    leading_repeated_slash_pattern = re.compile(r"^/{2,}")
    forward_slash_normalized_path = leading_repeated_slash_pattern.sub(
        "/",
        resolved_path.replace("\\", "/").lower().rstrip("/"),
    )
    system_temporary_root = leading_repeated_slash_pattern.sub(
        "/",
        os.path.normpath(tempfile.gettempdir()).replace("\\", "/").lower().rstrip("/"),
    )
    forbidden_bare_ephemeral_roots = {"/tmp", "/temp", "/worktrees", "/worktree", system_temporary_root}
    return forward_slash_normalized_path in forbidden_bare_ephemeral_roots


def _path_is_bare_named_worktrees_container(resolved_path: str) -> bool:
    return Path(resolved_path).name.lower() in ("worktrees", "worktree")


def _path_basename_is_shell_glob_wildcard(resolved_path: str) -> bool:
    bracket_class_empty_length = len("[]")
    basename = Path(resolved_path).name
    if not basename:
        return False
    if basename in ("*", "?"):
        return True
    if basename.startswith("[") and basename.endswith("]") and len(basename) > bracket_class_empty_length:
        return True
    if "*" in basename or "?" in basename:
        return True
    return False


def _command_contains_windows_style_path(command: str) -> bool:
    windows_drive_path_pattern = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:\\")
    windows_unc_path_pattern = re.compile(r"(?<!\S)\\\\[^\s\\]+\\[^\s\\]+")
    return bool(
        windows_drive_path_pattern.search(command)
        or windows_unc_path_pattern.search(command)
    )


def _split_command_preserving_windows_backslashes(command: str) -> list[str]:
    if "\\" in command and (
        os.name == "nt" or _command_contains_windows_style_path(command)
    ):
        forward_slash_normalized_command = command.replace("\\", "/")
        return shlex.split(forward_slash_normalized_command)
    return shlex.split(command)


def _rm_flags_before_double_dash_are_unsafe(tokens_after_rm: list[str]) -> bool:
    safe_long_options = frozenset({
        "--recursive",
        "--force",
        "--verbose",
        "--interactive",
        "--dir",
    })
    for each_token in tokens_after_rm:
        if each_token == "--":
            return False
        if not each_token.startswith("-"):
            continue
        if "=" in each_token:
            return True
        if each_token.startswith("--"):
            if each_token not in safe_long_options:
                return True
            continue
        short_rest = each_token[1:]
        if not short_rest or not all(c in "rfRvidI" for c in short_rest):
            return True
    return False


def _collect_rm_target_tokens(tokens_after_rm: list[str]) -> list[str]:
    targets: list[str] = []
    has_seen_end_of_options = False
    for each_token in tokens_after_rm:
        if not has_seen_end_of_options and each_token == "--":
            has_seen_end_of_options = True
            continue
        if not has_seen_end_of_options and each_token.startswith("-"):
            continue
        targets.append(each_token)
    return targets


def rm_targets_only_ephemeral_paths(command: str) -> bool:
    """Return True when command is a single rm invocation whose every target is inside an ephemeral directory.

    Refuses compound commands so operators like && / || / ; / | / backticks /
    $(...) cannot piggy-back non-rm work on the ephemeral auto-allow. Rejects
    bare ephemeral roots (/tmp, system temp dir) and bare directories named
    worktrees/worktree so we never auto-approve wiping those roots. Only
    allows common short flags and a small set of long options before ``--``;
    tokens with ``=`` or unknown long options disable auto-allow.
    """
    compound_shell_operator_pattern = re.compile(r'(?:&&|\|\||;|\||`|\$\()')
    if compound_shell_operator_pattern.search(command):
        return False
    try:
        all_command_tokens = _split_command_preserving_windows_backslashes(command)
    except ValueError:
        return False
    if len(all_command_tokens) < 2 or all_command_tokens[0] != "rm":
        return False
    tokens_after_rm = all_command_tokens[1:]
    if _rm_flags_before_double_dash_are_unsafe(tokens_after_rm):
        return False
    all_target_tokens = _collect_rm_target_tokens(tokens_after_rm)
    if not all_target_tokens:
        return False
    for each_target_token in all_target_tokens:
        each_resolved_path = os.path.normpath(os.path.expanduser(each_target_token))
        if _path_basename_is_shell_glob_wildcard(each_resolved_path):
            return False
        if _path_is_bare_ephemeral_root(each_resolved_path):
            return False
        if _path_is_bare_named_worktrees_container(each_resolved_path):
            return False
        if not directory_is_ephemeral(each_resolved_path):
            return False
    return True


def _destructive_match_is_rm_family(matched_description: str) -> bool:
    """Return True when the matched destructive pattern is one of the rm-family deletes.

    The rm-family descriptions all begin with the same prefix; the compound
    ephemeral auto-allow and the quoted-mention guard act only on these, never on
    git, database, or device patterns.

    Args:
        matched_description: A description from DESTRUCTIVE_BASH_PATTERNS.

    Returns:
        True when the description names an rm deletion.
    """
    rm_family_description_prefix = "rm "
    return matched_description.startswith(rm_family_description_prefix)


def _command_contains_shell_expansion(command: str) -> bool:
    """Return True when the command contains shell parameter or command expansion.

    Any ``$`` (variable reference or ``$(...)`` command substitution) or backtick
    subshell means a token could expand at runtime to ``rm`` or to an arbitrary
    destructive command that the hook cannot resolve statically. The quoted-mention
    guard and the compound ephemeral auto-allow both fail closed on this so they
    never grant on a command whose effective program list is unknown until the
    shell runs.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when the command contains a ``$`` or backtick expansion character.
    """
    return "$" in command or "`" in command


def _split_tokens_into_shell_segments(all_command_tokens: list[str]) -> list[list[str]]:
    """Split a shlex token list into simple-command segments on control operators.

    Segments are delimited by ``&&``, ``||``, ``;``, ``|`` and ``&`` tokens, so
    each returned segment is one simple command. Operators that are not whitespace
    separated stay inside one shlex token and therefore inside one segment; that
    segment fails the absolute-ephemeral target check and the command falls through
    to the prompt.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        A list of segments, each a list of tokens with operators removed.
    """
    all_segments: list[list[str]] = []
    current_segment: list[str] = []
    for each_token in all_command_tokens:
        if each_token in ALL_SHELL_CONTROL_OPERATOR_TOKENS:
            all_segments.append(current_segment)
            current_segment = []
            continue
        current_segment.append(each_token)
    all_segments.append(current_segment)
    return all_segments


def _leading_command_token(all_command_tokens: list[str]) -> str | None:
    """Return the program token that leads the command, skipping VAR=value prefixes.

    A shell command may begin with one or more ``NAME=value`` environment
    assignments (``FOO=bar rm -rf x``); the first token that is not such an
    assignment is the program the shell executes. Returns None when every token is
    an assignment or the list is empty.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        The leading program token, or None when there is no program token.
    """
    leading_assignment_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
    for each_token in all_command_tokens:
        if leading_assignment_pattern.match(each_token):
            continue
        return each_token
    return None


def _command_executes_a_string_argument(all_command_tokens: list[str]) -> bool:
    """Return True when the command's leading program runs a string argument as code.

    Shell interpreters and wrappers (``bash``, ``sh``, ``eval``, ``sudo``,
    ``xargs`` and the rest of ALL_INTERPRETER_AND_WRAPPER_COMMANDS) and remote
    runners such as ``ssh`` execute a following quoted token as a command line, so
    ``bash -c 'rm -rf /etc'`` and ``ssh host 'rm -rf /etc'`` run ``rm`` even though
    no token's basename is ``rm``. Language interpreters (``python``, ``perl``,
    ``ruby``, ``node`` and the rest of ALL_REMOTE_AND_PROGRAM_STRING_EXECUTORS) run
    a string only with a ``-c`` or ``-e`` flag, so those qualify only when such a
    flag is present.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        True when the leading program executes a quoted string argument as code.
    """
    leading_command_token = _leading_command_token(all_command_tokens)
    if leading_command_token is None:
        return False
    leading_command_basename = Path(leading_command_token).name.lower()
    if leading_command_basename in ALL_INTERPRETER_AND_WRAPPER_COMMANDS:
        return True
    if leading_command_basename not in ALL_REMOTE_AND_PROGRAM_STRING_EXECUTORS:
        return False
    if leading_command_basename == "ssh":
        return True
    return any(
        each_token in ALL_STRING_ARGUMENT_EXECUTION_FLAGS for each_token in all_command_tokens
    )


def _explode_glued_shell_control_operators(all_command_tokens: list[str]) -> list[str]:
    """Split control operators off shlex tokens that glue them to a program name.

    shlex keeps a control operator joined to an adjacent program when no whitespace
    separates them, so ``true; eval 'x'`` tokenizes to ``['true;', 'eval', 'x']``
    with the ``;`` hidden inside ``true;``. This re-splits each token on the
    unquoted control operators ``&&`` / ``||`` / ``;`` / ``|`` / ``&`` so the
    operator becomes its own token and segment boundaries are visible. shlex has
    already removed quoting, so any operator character still present in a token came
    from unquoted shell source and is a real boundary.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        Tokens with glued control operators separated into standalone tokens.
    """
    control_operator_split_pattern = re.compile(r"(&&|\|\||;|\||&)")
    all_exploded_tokens: list[str] = []
    for each_token in all_command_tokens:
        for each_fragment in control_operator_split_pattern.split(each_token):
            if each_fragment:
                all_exploded_tokens.append(each_fragment)
    return all_exploded_tokens


def _any_shell_segment_executes_a_string_argument(all_command_tokens: list[str]) -> bool:
    """Return True when any shell segment's leading program runs a string as code.

    Splits the command into simple-command segments on ``&&`` / ``||`` / ``;`` /
    ``|`` / ``&`` and applies the leading-program string-execution check to each.
    A benign program leading the whole command (``echo hi && bash -c 'rm -rf /etc'``,
    ``true; eval 'rm -rf /etc'``) must not mask an interpreter that runs the
    destructive ``rm`` inside a later segment, so every segment is inspected rather
    than only the command's first program. Control operators glued to a program by
    missing whitespace are separated first so those segment boundaries are seen.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        True when at least one segment's leading program executes a quoted string
        argument as code.
    """
    all_exploded_tokens = _explode_glued_shell_control_operators(all_command_tokens)
    for each_segment in _split_tokens_into_shell_segments(all_exploded_tokens):
        if each_segment and _command_executes_a_string_argument(each_segment):
            return True
    return False


def command_has_no_real_rm_invocation(command: str) -> bool:
    """Return True when no shell token in the command actually invokes ``rm``.

    Distinguishes a destructive-pattern match that lands inside a quoted string
    argument (``grep 'rm -rf foo' log``, ``echo "rm -rf x"``,
    ``git commit -m "rm -rf cleanup"``) from a command that runs ``rm``. A quoted
    mention tokenizes to a single token whose path basename is not ``rm``, so it is
    reported as having no real invocation and the spurious ``rm`` prompt is
    suppressed.

    Fails closed (returns False, meaning "treat as a real invocation, keep
    prompting") when the command contains shell expansion (``$`` or backtick),
    where a token such as ``$RM`` could expand to ``rm``; when tokenization fails on
    unbalanced quotes; or when any shell segment's leading program executes a quoted
    string argument as code (``bash -c 'rm -rf /etc'``, ``eval 'rm -rf /etc'``,
    ``ssh host 'rm -rf /etc'``, ``awk 'BEGIN{system("rm -rf /etc")}'``,
    ``echo hi && bash -c 'rm -rf /etc'``), where the destructive ``rm`` rides inside
    an executed string rather than a passive mention. The per-segment check means a
    benign leader on the whole command does not mask an interpreter in a later
    segment. ``/bin/rm``, ``sudo rm`` and ``\\rm`` each tokenize to a token whose
    basename is ``rm`` and are correctly reported as real.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when the command contains no real ``rm`` invocation.
    """
    if _command_contains_shell_expansion(command):
        return False
    try:
        all_command_tokens = _split_command_preserving_windows_backslashes(command)
    except ValueError:
        return False
    if _any_shell_segment_executes_a_string_argument(all_command_tokens):
        return False
    for each_token in all_command_tokens:
        if Path(each_token).name == "rm":
            return False
    return True


def _find_non_rm_destructive_pattern(command: str) -> str | None:
    """Return the first non-rm-family destructive pattern description, or None.

    Applied after the quoted-mention guard finds a matched rm-family pattern to be
    a false positive: the command is rescanned for any other destructive pattern
    (force push, git clean, mkfs, dd, DROP/TRUNCATE, signing bypass) so a real
    non-rm hazard riding alongside the quoted mention
    (``grep 'rm -rf' f && git push --force origin main``) still prompts.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        The description of the first matching non-rm-family pattern, or None.
    """
    for each_pattern_regex, each_pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if _destructive_match_is_rm_family(each_pattern_description):
            continue
        if each_pattern_regex.search(command):
            return each_pattern_description
    return None


def _command_contains_non_rm_family_destructive_pattern(command: str) -> bool:
    """Return True when any destructive pattern in the command is not rm-family.

    The compound ephemeral auto-allow grants only when every destructive pattern
    present is an rm deletion. A git reset --hard, force push, git clean, mkfs, dd,
    or DROP/TRUNCATE riding inside the chain is not bounded by the ephemeral rm
    targets, so its presence declines the whole auto-allow.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when at least one matching destructive pattern is not rm-family.
    """
    for each_pattern_regex, each_pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if each_pattern_regex.search(command) and not _destructive_match_is_rm_family(
            each_pattern_description
        ):
            return True
    return False


def _rm_segment_targets_only_absolute_ephemeral_paths(all_rm_segment_tokens: list[str]) -> bool:
    """Return True when an ``rm`` segment's every target is an absolute ephemeral path.

    ``all_rm_segment_tokens`` is one shell segment beginning at its ``rm`` command
    token. Rejects the segment (returns False) when an unsafe flag precedes ``--``,
    when there are no targets, when a target is relative (the compound auto-allow
    refuses to resolve relative targets without a trusted working directory), when
    a target basename is a glob wildcard, when a target is a bare ephemeral root or
    a bare worktrees container, or when a target is not inside an ephemeral
    directory.

    Args:
        all_rm_segment_tokens: Shlex tokens of a single ``rm`` segment, the first
            token being the ``rm`` command.

    Returns:
        True when every target is an absolute ephemeral path safe to auto-allow.
    """
    tokens_after_rm = all_rm_segment_tokens[1:]
    if _rm_flags_before_double_dash_are_unsafe(tokens_after_rm):
        return False
    all_target_tokens = _collect_rm_target_tokens(tokens_after_rm)
    if not all_target_tokens:
        return False
    for each_target_token in all_target_tokens:
        each_expanded_target = os.path.expanduser(each_target_token)
        each_is_absolute = (
            os.path.isabs(each_expanded_target)
            or each_expanded_target.replace("\\", "/").startswith("/")
        )
        if not each_is_absolute:
            return False
        each_resolved_target = os.path.normpath(each_expanded_target)
        if _path_basename_is_shell_glob_wildcard(each_resolved_target):
            return False
        if _path_is_bare_ephemeral_root(each_resolved_target):
            return False
        if _path_is_bare_named_worktrees_container(each_resolved_target):
            return False
        if not directory_is_ephemeral(each_resolved_target):
            return False
    return True


def rm_compound_targets_only_absolute_ephemeral_paths(command: str) -> bool:
    """Return True when a compound command's every ``rm`` segment is safe to auto-allow.

    Handles destructive cleanup chains that declare no ephemeral working directory,
    such as ``rm -rf /tmp/pr136 /tmp/difftest && echo 'cleaned'``. Splits the
    command into shell segments and requires all of: at least one segment runs
    ``rm``; every ``rm`` segment targets only absolute ephemeral paths; no segment's
    leading command is a shell interpreter, ``eval``, ``exec``, ``source`` or a
    privilege or argument wrapper (``sudo``, ``su``, ``env``, ``xargs``); no segment
    matches a destructive pattern that is not rm-family (force push, git clean,
    git reset --hard, mkfs, dd, DROP/TRUNCATE, signing bypass); and the command
    contains no shell expansion.

    Fails closed (returns False) on shell expansion (``$`` or backtick), on a
    tokenization error, and whenever any ``rm`` segment fails the absolute-ephemeral
    target check, so the compound auto-allow grants only on chains it can fully
    bound.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when every ``rm`` segment targets only absolute ephemeral paths and no
        other hazard is present.
    """
    if _command_contains_shell_expansion(command):
        return False
    if _command_contains_non_rm_family_destructive_pattern(command):
        return False
    try:
        all_command_tokens = _split_command_preserving_windows_backslashes(command)
    except ValueError:
        return False
    has_seen_rm_segment = False
    for each_segment in _split_tokens_into_shell_segments(all_command_tokens):
        if not each_segment:
            continue
        if Path(each_segment[0]).name.lower() in ALL_INTERPRETER_AND_WRAPPER_COMMANDS:
            return False
        each_rm_token_index = next(
            (
                index
                for index, token in enumerate(each_segment)
                if Path(token).name == "rm"
            ),
            None,
        )
        if each_rm_token_index is None:
            continue
        has_seen_rm_segment = True
        if not _rm_segment_targets_only_absolute_ephemeral_paths(
            each_segment[each_rm_token_index:]
        ):
            return False
    return has_seen_rm_segment


def targets_only_claude_directory(command: str) -> bool:
    """Check if rm command targets only paths under ~/.claude/."""
    all_rm_target_paths = re.findall(
        r'(?:rm\s+(?:-\w+\s+)*)("[^"]+"|\'[^\']+\'|\S+)',
        command,
    )
    if not all_rm_target_paths:
        return False

    for each_raw_path in all_rm_target_paths:
        each_stripped_path = each_raw_path.strip("\"'")
        each_cleaned_path = re.split(r'[;&|]', each_stripped_path)[0]
        if each_cleaned_path != each_stripped_path:
            return False
        each_resolved_path = os.path.normpath(os.path.expanduser(each_cleaned_path))
        if not each_resolved_path.startswith(CLAUDE_DIRECTORY_PATH):
            return False

    return True


def _ephemeral_recursive_rm_auto_allow_granted(command: str, matched_description: str) -> bool:
    return matched_description.startswith(("rm -rf", "rm --recursive")) and rm_targets_only_ephemeral_paths(command)


def _extract_leading_cd_target(command: str) -> str | None:
    """Return the target of a ``cd`` that starts the command, or None if absent.

    Uses ``shlex.split`` with POSIX rules to tokenize the command so adjacent
    quoted string concatenation (``"/tmp/a""/../../etc"``) resolves to the
    same path the shell would cd to (``/tmp/a/../../etc``). A regex-based
    extractor cannot see past the first quoted segment and would
    misclassify the cd target as ephemeral while the shell ends up
    somewhere else entirely.

    Returns None when the command does not start with ``cd``, when tokenization
    fails (unbalanced quotes), when the cd target is missing, or when the
    target contains any shell-expansion character (``$`` for variable /
    command substitution, `` ` `` for backtick subshell) that the shell
    would resolve *before* cd runs. Hook authors cannot safely know what
    ``$(rm -rf ~)`` expands to, so the conservative answer is "don't
    auto-allow".
    """
    shell_expansion_characters_that_execute_code = ("$", "`")
    try:
        all_command_tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    if len(all_command_tokens) < 2 or all_command_tokens[0] != "cd":
        return None
    cd_target_token = all_command_tokens[1]
    for each_shell_expansion_character in shell_expansion_characters_that_execute_code:
        if each_shell_expansion_character in cd_target_token:
            return None
    return cd_target_token


def _resolve_declared_effective_working_directory(command: str, tool_input: dict) -> str | None:
    """Return the declared cwd for the command, or None when none is declared.

    Precedence: leading ``cd "X"`` in the command, then the
    ``tool_input['cwd']`` field passed in by the Bash tool call. Returns
    None when neither source is present so the broad auto-allow gate never
    depends on the hook process's own ``os.getcwd()`` (which can itself be
    ephemeral when Claude Code runs inside a worktree, and would otherwise
    auto-allow every destructive command). Paths are user-expanded and
    normalized so downstream ``directory_is_ephemeral`` comparisons see a
    canonical form on both POSIX and Windows.
    """
    leading_cd_target = _extract_leading_cd_target(command)
    if leading_cd_target is not None:
        return os.path.normpath(os.path.expanduser(leading_cd_target))
    tool_input_cwd_value = tool_input.get("cwd") if isinstance(tool_input, dict) else None
    if isinstance(tool_input_cwd_value, str) and tool_input_cwd_value.strip():
        return os.path.normpath(os.path.expanduser(tool_input_cwd_value))
    return None


def _effective_working_directory_is_ephemeral(command: str, tool_input: dict) -> bool:
    """Return True when the command's declared effective cwd is a specific ephemeral directory.

    Auto-allow trust model: if the destructive command declares (via leading
    ``cd`` or ``tool_input['cwd']``) that it will execute inside a concrete
    ephemeral directory (a temp-dir subfolder, a git worktrees directory, or
    a subfolder of the OS temp root), treat that directory as a disposable
    trust boundary and skip the destructive-action prompt. Rejects bare
    ephemeral roots (``/tmp``, ``/temp``, the OS temp root, ``/worktrees``,
    ``/worktree``) so auto-allow only triggers inside a named scratch area,
    not at the root of a shared scratch namespace. Returns False when no
    cwd is declared; the narrower target-based auto-allow still applies in
    that case.
    """
    declared_effective_cwd = _resolve_declared_effective_working_directory(command, tool_input)
    if declared_effective_cwd is None:
        return False
    if _path_is_bare_ephemeral_root(declared_effective_cwd):
        return False
    return directory_is_ephemeral(declared_effective_cwd)


CWD_SCOPED_DESTRUCTIVE_DESCRIPTIONS_ELIGIBLE_FOR_BROAD_EPHEMERAL_AUTO_ALLOW = (
    "rm -rf",
    "rm --recursive",
    "git reset --hard",
)


def _destructive_match_is_cwd_scoped(matched_description: str) -> bool:
    """Return True when the matched destructive pattern's blast radius is bounded by cwd.

    ``rm -rf``, ``rm --recursive``, and ``git reset --hard`` only affect
    files inside the working directory (or paths resolved relative to it
    when the rm target is relative). Patterns whose blast radius is NOT
    bounded by cwd — ``git push --force`` / ``git push -f`` (remote
    history rewrite), ``git clean`` variants (untracked deletion outside
    what the user can audit at the current prompt), ``mkfs`` / ``dd``
    (raw device), ``DROP TABLE`` / ``DROP DATABASE`` / ``TRUNCATE TABLE``
    (database) — must still prompt even when the command runs from an
    ephemeral worktree. Being in a scratch directory is not a trust zone
    for remote or out-of-band effects.
    """
    return matched_description.startswith(
        CWD_SCOPED_DESTRUCTIVE_DESCRIPTIONS_ELIGIBLE_FOR_BROAD_EPHEMERAL_AUTO_ALLOW
    )


def _command_contains_any_non_cwd_scoped_destructive_pattern(command: str) -> bool:
    """Return True when the command matches any destructive pattern outside the cwd-scoped whitelist.

    ``find_destructive_pattern`` returns the *first* match in the
    ``DESTRUCTIVE_BASH_PATTERNS`` table, where ``rm -rf`` sits at the
    very front. That means a compound like ``cd /tmp/scratch && rm -rf
    cache && git push --force`` reports ``rm -rf`` to the main gate,
    passes the cwd-scoped whitelist, and ends up auto-allowing the
    remote force-push even though the whitelist docstring says
    non-cwd-scoped patterns must still prompt. This helper scans *every*
    destructive pattern and returns True the moment it finds one that
    is not in the cwd-scoped whitelist, so the broad auto-allow can
    decline the whole command rather than trust the first-match report.
    """
    for each_pattern_regex, each_pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if each_pattern_regex.search(command) and not each_pattern_description.startswith(
            CWD_SCOPED_DESTRUCTIVE_DESCRIPTIONS_ELIGIBLE_FOR_BROAD_EPHEMERAL_AUTO_ALLOW
        ):
            return True
    return False


def _command_rm_targets_include_unsafe_path(command: str, tool_input: dict) -> bool:
    """Return True when the command contains an ``rm`` whose targets are unsafe.

    Unsafe means any of: bare ephemeral root (``/tmp``, ``/temp``, the OS
    temp root, ``/worktrees``, ``/worktree``), bare named worktrees
    container, absolute path outside the ephemeral namespace, relative
    path that resolves (against the declared effective cwd) outside the
    ephemeral namespace, wildcard glob metacharacter in the target
    basename, or unsafe ``rm`` flag before ``--`` (``--files0-from=...``,
    unknown long option, non-whitelisted short flag) as enforced by
    ``_rm_flags_before_double_dash_are_unsafe``.

    Fails closed: returns True on parse failure (``ValueError`` from
    unbalanced quotes) or when a relative target is encountered without
    a declared effective cwd to resolve it against. The broad auto-allow
    must decline rather than grant on input the hook cannot conclusively
    bound.
    """
    try:
        all_command_tokens = _split_command_preserving_windows_backslashes(command)
    except ValueError:
        return True
    declared_effective_cwd = _resolve_declared_effective_working_directory(command, tool_input)
    for each_token_index in range(len(all_command_tokens)):
        if all_command_tokens[each_token_index] != "rm":
            continue
        tokens_after_rm = all_command_tokens[each_token_index + 1:]
        if _rm_flags_before_double_dash_are_unsafe(tokens_after_rm):
            return True
        all_target_tokens = _collect_rm_target_tokens(tokens_after_rm)
        for each_target_token in all_target_tokens:
            each_expanded_target = os.path.expanduser(each_target_token)
            each_is_absolute = (
                os.path.isabs(each_expanded_target)
                or each_expanded_target.replace("\\", "/").startswith("/")
            )
            if each_is_absolute:
                each_resolved_target = os.path.normpath(each_expanded_target)
            else:
                if declared_effective_cwd is None:
                    return True
                each_resolved_target = os.path.normpath(
                    os.path.join(declared_effective_cwd, each_expanded_target)
                )
            if _path_basename_is_shell_glob_wildcard(each_resolved_target):
                return True
            if _path_is_bare_ephemeral_root(each_resolved_target):
                return True
            if _path_is_bare_named_worktrees_container(each_resolved_target):
                return True
            if not directory_is_ephemeral(each_resolved_target):
                return True
    return False


def _git_reset_hard_allowed_for_command(command: str, current_working_directory: str) -> bool:
    if directory_is_ephemeral(current_working_directory):
        return True
    current_working_directory_lowercased = os.path.normpath(current_working_directory).lower()
    for allowed_project in load_allow_git_reset_hard_projects():
        allowed_project_lowercased = os.path.normpath(allowed_project).lower()
        if current_working_directory_lowercased.startswith(allowed_project_lowercased):
            return True
        for path_match in re.findall(r'cd\s+"([^"]+)"', command):
            if os.path.normpath(path_match).lower().startswith(allowed_project_lowercased):
                return True
    return False


def _is_convergence_branch(branch: str) -> bool:
    all_convergence_branch_prefixes = ALL_CONVERGENCE_BRANCH_PREFIXES
    for each_prefix in all_convergence_branch_prefixes:
        if branch.startswith(each_prefix):
            return True
    return bool(re.match(CONVERGENCE_BRANCH_SUFFIX_PATTERN, branch))


def _all_refspecs_are_convergence_branches(post_remote_text: str) -> bool:
    if not post_remote_text.strip():
        return False
    is_any_refspec_checked = False
    for each_token in post_remote_text.split():
        if each_token.startswith("-"):
            continue
        is_any_refspec_checked = True
        destination_branch = each_token.split(":")[-1]
        if not _is_convergence_branch(destination_branch):
            return False
    return is_any_refspec_checked


def _force_push_targets_convergence_branch(command: str) -> bool:
    convergence_force_push_detection_pattern = (
        CONVERGENCE_FORCE_PUSH_DETECTION_PATTERN
    )
    is_force_push_found = False
    for each_match in re.finditer(
        convergence_force_push_detection_pattern, command, re.IGNORECASE
    ):
        is_force_push_found = True
        post_push_text = each_match.group(1).strip()
        all_tokens = post_push_text.split()
        remote_index = 1 if all_tokens and all_tokens[0] in ("--force", "-f") else 0
        all_refspec_tokens = [
            token for token in all_tokens[remote_index + 1 :]
            if token not in ("--force", "-f")
        ]
        post_remote_text = " ".join(all_refspec_tokens)
        if not post_remote_text:
            return False
        if not _all_refspecs_are_convergence_branches(post_remote_text):
            return False
    return is_force_push_found


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "")

    if gh_redirect_is_active():
        redirected_gh_description = find_redirected_gh_pattern(command)
        if redirected_gh_description is not None:
            print(json.dumps(_build_silent_gh_deny_response(redirected_gh_description)))
            sys.exit(0)

    matched_description = find_destructive_pattern(command)

    if (
        matched_description is not None
        and _destructive_match_is_rm_family(matched_description)
        and command_has_no_real_rm_invocation(command)
    ):
        matched_description = _find_non_rm_destructive_pattern(command)

    if matched_description is not None and targets_only_claude_directory(command):
        sys.exit(0)

    if (
        matched_description is not None
        and _destructive_match_is_cwd_scoped(matched_description)
        and _effective_working_directory_is_ephemeral(command, tool_input)
        and not _command_rm_targets_include_unsafe_path(command, tool_input)
        and not _command_contains_any_non_cwd_scoped_destructive_pattern(command)
    ):
        sys.exit(0)

    if matched_description is not None and _ephemeral_recursive_rm_auto_allow_granted(command, matched_description):
        sys.exit(0)

    if (
        matched_description is not None
        and _destructive_match_is_rm_family(matched_description)
        and rm_compound_targets_only_absolute_ephemeral_paths(command)
    ):
        sys.exit(0)

    if matched_description is not None and "git reset --hard" in matched_description:
        if _git_reset_hard_allowed_for_command(command, os.getcwd()):
            sys.exit(0)

    if (
        matched_description is not None
        and "git push" in matched_description
        and ("force" in matched_description or "-f" in matched_description)
        and _force_push_targets_convergence_branch(command)
    ):
        for each_pattern, each_description in DESTRUCTIVE_BASH_PATTERNS:
            if "git push" in each_description and ("force" in each_description or "-f" in each_description):
                continue
            if each_pattern.search(command):
                matched_description = each_description
                break
        else:
            sys.exit(0)

    if matched_description is not None:
        ask_response = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"DESTRUCTIVE: {matched_description}. Requires explicit user approval."
            }
        }
        print(json.dumps(ask_response))

    sys.exit(0)


if __name__ == "__main__":
    main()
