import re


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").lower()


def is_specific_file(path: str) -> bool:
    file_extension_pattern = re.compile(r"\.\w{1,10}$")
    return bool(file_extension_pattern.search(path))


def is_in_indexed_repo(path: str) -> bool:
    indexed_paths = (
        "y:/information technology/scripts/automation/python/cdp automations/",
        "y:/information technology/scripts/automation/python/",
        "c:/users/jon/.claude/",
        "y:/craft a tale/behavioral app/",
    )
    indexed_paths_wsl = (
        "/mnt/y/information technology/scripts/automation/python/cdp automations/",
        "/mnt/y/information technology/scripts/automation/python/",
        "/mnt/c/users/jon/.claude/",
        "/mnt/y/craft a tale/behavioral app/",
    )
    norm = normalize_path(path)
    if not norm.endswith("/"):
        norm += "/"
    for prefix in indexed_paths:
        if norm.startswith(prefix):
            return True
    for prefix in indexed_paths_wsl:
        if norm.startswith(prefix):
            return True
    return False
