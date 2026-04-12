import re
from typing import Final

INDEXED_PATHS: Final[tuple[str, ...]] = (
    "y:/information technology/scripts/automation/python/cdp automations/",
    "y:/information technology/scripts/automation/python/",
    "c:/users/jon/.claude/",
    "y:/craft a tale/behavioral app/",
)

INDEXED_PATHS_WSL: Final[tuple[str, ...]] = (
    "/mnt/y/information technology/scripts/automation/python/cdp automations/",
    "/mnt/y/information technology/scripts/automation/python/",
    "/mnt/c/users/jon/.claude/",
    "/mnt/y/craft a tale/behavioral app/",
)

_FILE_EXTENSION_PATTERN = re.compile(r"\.\w{1,10}$")


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").lower()


def is_specific_file(path: str) -> bool:
    return bool(_FILE_EXTENSION_PATTERN.search(path))


def is_in_indexed_repo(path: str) -> bool:
    norm = normalize_path(path)
    if not norm.endswith("/"):
        norm += "/"
    for prefix in INDEXED_PATHS:
        if norm.startswith(prefix):
            return True
    for prefix in INDEXED_PATHS_WSL:
        if norm.startswith(prefix):
            return True
    return False
