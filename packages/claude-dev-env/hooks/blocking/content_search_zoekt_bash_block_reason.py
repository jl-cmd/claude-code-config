import re
from typing import Final

_BASH_CONTENT_SEARCH_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"^\s*grep\s", re.IGNORECASE), "grep"),
    (re.compile(r"^\s*grep$", re.IGNORECASE), "grep"),
    (re.compile(r"\|\s*grep\s", re.IGNORECASE), "piped grep"),
    (re.compile(r"\|\s*grep$", re.IGNORECASE), "piped grep"),
    (re.compile(r"^\s*rg\s", re.IGNORECASE), "ripgrep"),
    (re.compile(r"^\s*rg$", re.IGNORECASE), "ripgrep"),
    (re.compile(r"\|\s*rg\s", re.IGNORECASE), "piped ripgrep"),
    (re.compile(r"^\s*findstr\s", re.IGNORECASE), "findstr"),
    (re.compile(r"^\s*Select-String", re.IGNORECASE), "PowerShell Select-String"),
    (re.compile(r"^\s*sls\s", re.IGNORECASE), "PowerShell sls"),
    (re.compile(r"^\s*ack\s", re.IGNORECASE), "ack"),
    (re.compile(r"^\s*ag\s", re.IGNORECASE), "silver searcher"),
    (re.compile(r"^\s*git\s+grep\s", re.IGNORECASE), "git grep"),
)


def block_reason_for_bash_command(command: str) -> str | None:
    for regex, command_name in _BASH_CONTENT_SEARCH_PATTERNS:
        if regex.search(command):
            return f"Bash({command_name})"
    return None
