import json
import os
import re
import sys
from pathlib import Path

import shlex

from _gh_body_arg_utils import (
    all_body_flag_prefixes,
    all_body_flags,
    body_file_flag,
    body_file_flag_prefix,
    body_file_short_flag,
    body_file_short_flag_prefix,
    count_extra_tokens_to_skip_for_split_quoted_value,
    get_logical_first_line,
    iter_significant_tokens,
)

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PR_GUIDE_PATH = os.path.join(PLUGIN_ROOT, "docs", "PR_DESCRIPTION_GUIDE.md")

REQUIRED_PR_SECTION_HEADERS = [
    "description",
    "why",
    "how",
]

MINIMUM_PR_BODY_LENGTH = 50

VAGUE_LANGUAGE_PATTERN = re.compile(
    r'\b(fix(?:ed)? (?:bug|issue|it)|update(?:d)? code|minor changes|various (?:fixes|updates|improvements))\b',
    re.IGNORECASE,
)


shell_variable_sigil: str = "$"
body_file_stdin_sentinel: str = "-"
all_quote_characters: frozenset[str] = frozenset({'"', "'"})
file_encoding_utf8: str = "utf-8"



class PathTraversalError(Exception):
    pass

def _is_flag_shaped_token(token: str) -> bool:
    if len(token) < 2:
        return False
    if not token.startswith("-"):
        return False
    return token[1] == "-" or token[1].isalpha()


def _strip_surrounding_quotes(token: str) -> str:
    if len(token) < 2:
        return token
    first_character = token[0]
    last_character = token[-1]
    if first_character in all_quote_characters and first_character == last_character:
        return token[1:-1]
    return token


def _is_unresolvable_shell_value(token: str) -> bool:
    return token.startswith(shell_variable_sigil)


def _read_body_file_contents(file_path: str) -> str | None:
    resolved_path = Path(file_path).resolve()
    allowed_root = Path.cwd().resolve()
    given_path = Path(file_path)
    if not given_path.is_absolute():
        try:
            resolved_path.relative_to(allowed_root)
        except ValueError:
            raise PathTraversalError("relative path resolves outside allowed root")
    if resolved_path.is_symlink():
        symlink_target = Path(os.readlink(str(resolved_path))).resolve()
        try:
            symlink_target.relative_to(allowed_root)
        except ValueError:
            raise PathTraversalError("symlink target resolves outside allowed root")
    try:
        with open(resolved_path, "r", encoding=file_encoding_utf8, errors="replace") as body_file:
            return body_file.read()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return None


def _resolve_body_file_value(raw_value_token: str) -> str | None:
    stripped_value = _strip_surrounding_quotes(raw_value_token)
    if not stripped_value:
        return ""
    if _is_unresolvable_shell_value(stripped_value):
        return ""
    if stripped_value == body_file_stdin_sentinel:
        return ""
    try:
        return _read_body_file_contents(stripped_value)
    except PathTraversalError:
        return None


def _resolve_body_string_value(raw_value_token: str) -> str:
    stripped_value = _strip_surrounding_quotes(raw_value_token)
    if _is_unresolvable_shell_value(stripped_value):
        return ""
    return stripped_value


def _reassemble_split_quoted_value(first_value_token: str, remaining_tokens: list[str]) -> str | None:
    extra_tokens_consumed = count_extra_tokens_to_skip_for_split_quoted_value(
        remaining_tokens,
        first_value_token,
    )
    if extra_tokens_consumed is None:
        return None
    if extra_tokens_consumed == 0:
        return first_value_token
    continuation_tokens = remaining_tokens[:extra_tokens_consumed]
    return " ".join([first_value_token, *continuation_tokens])


def _match_body_flag_equals_prefix(token: str) -> str | None:
    for each_prefix in all_body_flag_prefixes:
        if token.startswith(each_prefix):
            return each_prefix
    return None


def _match_body_file_equals_prefix(token: str) -> str | None:
    for each_prefix in (body_file_flag_prefix, body_file_short_flag_prefix):
        if token.startswith(each_prefix):
            return each_prefix
    return None


def _scan_raw_tokens_for_body(all_raw_tokens: list[str]) -> str | None | bool:
    """Return the body value from a raw token list, or False if no body flag found.

    Returns False when no body/body-file flag is present (caller should continue).
    Returns None when a body-file flag is present but malformed (no value follows).
    Returns str for body string values (may be empty for shell vars/sentinels).
    """
    token_index = 0
    while token_index < len(all_raw_tokens):
        current_token = all_raw_tokens[token_index]
        remaining_raw = all_raw_tokens[token_index + 1:]
        body_equals_prefix = _match_body_flag_equals_prefix(current_token)
        if body_equals_prefix is not None:
            first_value_token = current_token[len(body_equals_prefix):]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw)
            if full_value_token is None:
                return None
            return _resolve_body_string_value(full_value_token)
        body_file_equals_prefix = _match_body_file_equals_prefix(current_token)
        if body_file_equals_prefix is not None:
            first_value_token = current_token[len(body_file_equals_prefix):]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw)
            if full_value_token is None:
                return None
            return _resolve_body_file_value(full_value_token)
        if current_token in all_body_flags:
            if not remaining_raw or _is_flag_shaped_token(remaining_raw[0]):
                return None
            first_value_token = remaining_raw[0]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw[1:])
            if full_value_token is None:
                return None
            return _resolve_body_string_value(full_value_token)
        if current_token in {body_file_flag, body_file_short_flag}:
            if not remaining_raw or _is_flag_shaped_token(remaining_raw[0]):
                return None
            first_value_token = remaining_raw[0]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw[1:])
            if full_value_token is None:
                return None
            return _resolve_body_file_value(full_value_token)
        token_index += 1
    return False


def extract_body_from_command(command: str) -> str | None:
    """Return the PR body content for validation, or None if unextractable.

    Uses iter_significant_tokens to skip values of non-body value-taking flags
    so that --body/--body-file embedded in a quoted --title value never false-matches.
    For space-form body-file flags, scans the raw token list directly because
    iter_significant_tokens consumes the value token (yielding remaining-after-value).
    """
    logical_line = get_logical_first_line(command)
    if not logical_line:
        return None
    try:
        all_raw_tokens = shlex.split(logical_line, posix=False)
    except ValueError:
        return None
    try:
        all_significant_tokens = list(iter_significant_tokens(command))
    except ValueError:
        return None

    significant_token_set = {each_token for each_token, _ in all_significant_tokens}
    body_flag_found_in_significant = (
        any(each_token in all_body_flags for each_token in significant_token_set)
        or any(_match_body_flag_equals_prefix(each_token) is not None for each_token in significant_token_set)
        or any(_match_body_file_equals_prefix(each_token) is not None for each_token in significant_token_set)
        or any(each_token in {body_file_flag, body_file_short_flag} for each_token in significant_token_set)
    )
    if not body_flag_found_in_significant:
        return None

    result = _scan_raw_tokens_for_body(all_raw_tokens)
    if result is False:
        return None
    return result


def validate_pr_body(body: str) -> list[str]:
    violations = []
    body_lower = body.lower()

    missing_required_sections = [
        header for header in REQUIRED_PR_SECTION_HEADERS
        if f"## {header}" not in body_lower and f"**{header}" not in body_lower
    ]

    if missing_required_sections:
        formatted_sections = ", ".join(f"'{each_section.title()}'" for each_section in missing_required_sections)
        violations.append(f"Missing required section(s): {formatted_sections}")

    stripped_body = re.sub(r'#.*', '', body).strip()
    stripped_body = re.sub(r'\*\*.*?\*\*', '', stripped_body).strip()
    if len(stripped_body) < MINIMUM_PR_BODY_LENGTH:
        violations.append("PR body too short -- provide meaningful context for reviewers")

    vague_matches = VAGUE_LANGUAGE_PATTERN.findall(body)
    if vague_matches:
        violations.append(f"Vague language detected: {', '.join(vague_matches)} -- be specific about what changed and why")

    return violations


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    is_pr_create = "gh pr create" in command and ("--body" in command or "-b " in command)
    is_pr_edit = "gh pr edit" in command and "--body" in command

    if not (is_pr_create or is_pr_edit):
        sys.exit(0)

    body = extract_body_from_command(command)

    if not body:
        sys.exit(0)

    violations = validate_pr_body(body)

    if violations:
        violation_list = "; ".join(violations)
        pr_guide_reference = f" @{PR_GUIDE_PATH}" if os.path.exists(PR_GUIDE_PATH) else ""
        denial_reason = (
            f"BLOCKED: [PR_DESCRIPTION] {violation_list}. "
            f"Follow the PR description guide:{pr_guide_reference}"
        )
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": denial_reason,
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
