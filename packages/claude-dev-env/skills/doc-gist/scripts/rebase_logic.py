"""Rebase-mode data collection and HTML rendering for doc-gist.

Provides the public function `render_rebase_html` that orchestrates: ref
resolution, per-file numstat collection, range-diff parsing, per-file diff
extraction, and HTML rendering through the rebase template.
"""

from __future__ import annotations

import html as html_module
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_skill_root_path = str(Path(__file__).resolve().parent.parent)
if _skill_root_path not in sys.path:
    sys.path.insert(0, _skill_root_path)

from config import rebase_constants


@dataclass(frozen=True)
class Resolution:
    """A resolved git ref with its short sha and one-line subject."""

    label: str
    sha: str
    short: str
    subject: str


@dataclass(frozen=True)
class FileDelta:
    """Per-file additions and deletions in pre-rebase and post-rebase changesets."""

    path: str
    pre_additions: int
    pre_deletions: int
    post_additions: int
    post_deletions: int
    is_patch_replayed: bool = False

    @property
    def status(self) -> str:
        present_in_pre = self.pre_additions or self.pre_deletions
        present_in_post = self.post_additions or self.post_deletions
        if present_in_pre and not present_in_post:
            return rebase_constants.STATUS_LOST_LABEL
        if present_in_post and not present_in_pre:
            return rebase_constants.STATUS_GAINED_LABEL
        if self.is_patch_replayed:
            return rebase_constants.STATUS_PORTED_LABEL
        return rebase_constants.STATUS_MODIFIED_LABEL


@dataclass(frozen=True)
class CommitWalkRow:
    """One line from `git range-diff` parsed into structured fields."""

    status: str
    pre_index: str
    pre_sha: str
    post_index: str
    post_sha: str
    subject: str


def _safe_html(text: str) -> str:
    return html_module.escape(text, quote=True)


def _reject_unsafe_ref(ref: str) -> None:
    for each_character in rebase_constants.ALL_DANGEROUS_REF_CHARACTERS:
        if each_character in ref:
            raise SystemExit(f"Refusing unsafe ref: {ref!r}")


def _run_git(
    all_subcommand_args: tuple[str, ...],
    *extra_args: str,
    working_dir: Path,
    allow_failure: bool = False,
) -> str:
    full_command = ["git", *all_subcommand_args, *extra_args]
    completed = subprocess.run(
        full_command,
        cwd=str(working_dir),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0 and not allow_failure:
        message_text = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(f"git {' '.join(full_command[1:])} failed:\n{message_text}")
    return completed.stdout


def _resolve_optional_ref(ref: str, working_dir: Path) -> Optional[str]:
    git_output = _run_git(
        rebase_constants.ALL_GIT_REV_PARSE_VERIFY_QUIET_ARGS,
        ref,
        working_dir=working_dir,
        allow_failure=True,
    )
    sha = git_output.strip()
    return sha or None


def _resolve_required_ref(label: str, ref: str, working_dir: Path) -> Resolution:
    _reject_unsafe_ref(ref)
    sha = _resolve_optional_ref(ref, working_dir)
    if sha is None:
        raise SystemExit(
            f"Cannot resolve {label} ref {ref!r}. "
            f"If this is the pre-rebase ref, recover it from `git reflog` and pass it via --pre."
        )
    short = _run_git(
        rebase_constants.ALL_GIT_REV_PARSE_SHORT_ARGS, sha, working_dir=working_dir
    ).strip()
    subject = _run_git(
        rebase_constants.ALL_GIT_LOG_ONE_FORMAT_SUBJECT_ARGS, sha, working_dir=working_dir
    ).strip()
    return Resolution(label=ref, sha=sha, short=short, subject=subject)


def _detect_base_ref(post_sha: str, working_dir: Path) -> str:
    for each_candidate in rebase_constants.ALL_UPSTREAM_FALLBACK_REFS:
        candidate_sha = _resolve_optional_ref(each_candidate, working_dir)
        if candidate_sha is None:
            continue
        merge_attempt = _run_git(
            rebase_constants.ALL_GIT_MERGE_BASE_ARGS,
            candidate_sha,
            post_sha,
            working_dir=working_dir,
            allow_failure=True,
        )
        if merge_attempt.strip():
            return each_candidate
    raise SystemExit(
        "Could not auto-detect a rebase base. Pass --base <ref> "
        "(typical values: main, master, origin/main)."
    )


def _parse_shortstat(text: str) -> tuple[int, int, int]:
    files = 0
    additions = 0
    deletions = 0
    if not text.strip():
        return files, additions, deletions
    for each_fragment in text.strip().split(", "):
        fragment_words = each_fragment.split()
        if not fragment_words:
            continue
        leading_number = fragment_words[0]
        if not leading_number.isdigit():
            continue
        number_value = int(leading_number)
        if "file" in each_fragment:
            files = number_value
        elif "insertion" in each_fragment:
            additions = number_value
        elif "deletion" in each_fragment:
            deletions = number_value
    return files, additions, deletions


def _collect_numstat(
    base_ref: str, tip_ref: str, working_dir: Path
) -> dict[str, tuple[int, int]]:
    git_output = _run_git(
        rebase_constants.ALL_GIT_DIFF_NUMSTAT_ARGS,
        f"{base_ref}...{tip_ref}",
        working_dir=working_dir,
    )
    rows_by_path: dict[str, tuple[int, int]] = {}
    for each_line in git_output.splitlines():
        if "\t" not in each_line:
            continue
        adds_text, _, remainder = each_line.partition("\t")
        dels_text, _, path = remainder.partition("\t")
        if not path.strip():
            continue
        adds_value = int(adds_text) if adds_text.isdigit() else 0
        dels_value = int(dels_text) if dels_text.isdigit() else 0
        rows_by_path[path] = (adds_value, dels_value)
    return rows_by_path


def _resolve_blob_hash(tip_ref: str, target_path: str, working_dir: Path) -> Optional[str]:
    completed = subprocess.run(
        ["git", *rebase_constants.ALL_GIT_REV_PARSE_VERIFY_QUIET_ARGS, f"{tip_ref}:{target_path}"],
        cwd=str(working_dir),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        return None
    blob_hash = completed.stdout.strip()
    return blob_hash or None


def _compose_file_deltas(
    all_pre_files: dict[str, tuple[int, int]],
    all_post_files: dict[str, tuple[int, int]],
    pre_ref: str,
    post_ref: str,
    working_dir: Path,
) -> list[FileDelta]:
    every_path = sorted(set(all_pre_files.keys()) | set(all_post_files.keys()))
    deltas: list[FileDelta] = []
    for each_path in every_path:
        pre_adds, pre_dels = all_pre_files.get(each_path, (0, 0))
        post_adds, post_dels = all_post_files.get(each_path, (0, 0))
        is_in_both_changesets = (
            each_path in all_pre_files and each_path in all_post_files
        )
        if is_in_both_changesets:
            pre_blob = _resolve_blob_hash(pre_ref, each_path, working_dir)
            post_blob = _resolve_blob_hash(post_ref, each_path, working_dir)
            is_patch_replayed = (
                pre_blob is not None
                and post_blob is not None
                and pre_blob == post_blob
            )
        else:
            is_patch_replayed = False
        deltas.append(
            FileDelta(
                path=each_path,
                pre_additions=pre_adds,
                pre_deletions=pre_dels,
                post_additions=post_adds,
                post_deletions=post_dels,
                is_patch_replayed=is_patch_replayed,
            )
        )
    return deltas


def _collect_commit_walk(
    base_ref: str, pre_ref: str, post_ref: str, working_dir: Path
) -> list[CommitWalkRow]:
    git_output = _run_git(
        rebase_constants.ALL_GIT_RANGE_DIFF_NO_COLOR_ARGS,
        f"{base_ref}..{pre_ref}",
        f"{base_ref}..{post_ref}",
        working_dir=working_dir,
        allow_failure=True,
    )
    pattern = re.compile(rebase_constants.RANGE_DIFF_LINE_REGEX)
    rows: list[CommitWalkRow] = []
    for each_line in git_output.splitlines():
        match = pattern.match(each_line)
        if not match:
            continue
        rows.append(
            CommitWalkRow(
                status=match.group("status"),
                pre_index=match.group("pre_index"),
                pre_sha=match.group("pre_sha"),
                post_index=match.group("post_index"),
                post_sha=match.group("post_sha"),
                subject=match.group("subject"),
            )
        )
    return rows


def _detect_repo_root(working_dir: Path) -> Path:
    git_output = _run_git(
        rebase_constants.ALL_GIT_REV_PARSE_SHOW_TOPLEVEL_ARGS,
        working_dir=working_dir,
    ).strip()
    if not git_output:
        raise SystemExit("Not inside a git repository.")
    return Path(git_output)


def _detect_branch_name(working_dir: Path) -> str:
    git_output = _run_git(
        rebase_constants.ALL_GIT_REV_PARSE_ABBREV_REF_HEAD_ARGS,
        working_dir=working_dir,
    ).strip()
    return git_output or rebase_constants.DETACHED_HEAD_LABEL


def _count_commits(base_ref: str, tip_ref: str, working_dir: Path) -> int:
    git_output = _run_git(
        rebase_constants.ALL_GIT_REV_LIST_COUNT_ARGS,
        f"{base_ref}..{tip_ref}",
        working_dir=working_dir,
    ).strip()
    return int(git_output) if git_output.isdigit() else 0


def _collect_per_file_diff(
    base_ref: str, tip_ref: str, target_path: str, working_dir: Path
) -> str:
    return _run_git(
        rebase_constants.ALL_GIT_DIFF_PATCH_ARGS,
        f"{base_ref}...{tip_ref}",
        rebase_constants.PATH_SEPARATOR_FOR_DIFF,
        target_path,
        working_dir=working_dir,
        allow_failure=True,
    )


def _count_diff_sides(diff_text: str) -> tuple[int, int]:
    additions = 0
    deletions = 0
    for each_line in diff_text.splitlines():
        if each_line.startswith(rebase_constants.DIFF_HEADER_OLD_FILE_PREFIX):
            continue
        if each_line.startswith(rebase_constants.DIFF_HEADER_NEW_FILE_PREFIX):
            continue
        if each_line.startswith(rebase_constants.DIFF_HUNK_PREFIX):
            continue
        if each_line.startswith(rebase_constants.DIFF_ADDITION_PREFIX):
            additions += 1
            continue
        if each_line.startswith(rebase_constants.DIFF_DELETION_PREFIX):
            deletions += 1
    return additions, deletions


def _format_filtered_diff_pre(diff_text: str, keep_side: str) -> str:
    line_limit = rebase_constants.DIFF_LINE_LIMIT_PER_FILE
    rendered_segments: list[str] = []
    has_truncation = False
    emitted_count = 0
    keep_additions = keep_side == rebase_constants.STATUS_GAINED_LABEL
    for each_line in diff_text.splitlines():
        if (
            each_line.startswith(rebase_constants.DIFF_HEADER_DIFF_PREFIX)
            or each_line.startswith(rebase_constants.DIFF_HEADER_INDEX_PREFIX)
            or each_line.startswith(rebase_constants.DIFF_HEADER_OLD_FILE_PREFIX)
            or each_line.startswith(rebase_constants.DIFF_HEADER_NEW_FILE_PREFIX)
        ):
            rendered_segments.append(f'<span class="c">{_safe_html(each_line)}</span>\n')
            continue
        if each_line.startswith(rebase_constants.DIFF_HUNK_PREFIX):
            if emitted_count >= line_limit:
                has_truncation = True
                break
            rendered_segments.append(f'<span class="h">{_safe_html(each_line)}</span>\n')
            emitted_count += 1
            continue
        if each_line.startswith(rebase_constants.DIFF_ADDITION_PREFIX):
            if not keep_additions:
                continue
            if emitted_count >= line_limit:
                has_truncation = True
                break
            rendered_segments.append(f'<span class="a">{_safe_html(each_line)}</span>\n')
            emitted_count += 1
            continue
        if each_line.startswith(rebase_constants.DIFF_DELETION_PREFIX):
            if keep_additions:
                continue
            if emitted_count >= line_limit:
                has_truncation = True
                break
            rendered_segments.append(f'<span class="d">{_safe_html(each_line)}</span>\n')
            emitted_count += 1
            continue
        if emitted_count >= line_limit:
            has_truncation = True
            break
        rendered_segments.append(f'<span class="c">{_safe_html(each_line)}</span>\n')
        emitted_count += 1
    if has_truncation:
        rendered_segments.append(
            f'<span class="truncated">… truncated at {line_limit} lines …</span>'
        )
    return "".join(rendered_segments).rstrip("\n")


def _render_split_diff_panels(diff_text: str) -> str:
    if not diff_text.strip():
        return '<p class="empty-diff">No diff content for this file.</p>'
    additions, deletions = _count_diff_sides(diff_text)
    if deletions > 0:
        removals_inner = (
            f"<pre>{_format_filtered_diff_pre(diff_text, rebase_constants.STATUS_LOST_LABEL)}</pre>"
        )
    else:
        removals_inner = '<div class="empty-side">No removals.</div>'
    if additions > 0:
        additions_inner = (
            f"<pre>{_format_filtered_diff_pre(diff_text, rebase_constants.STATUS_GAINED_LABEL)}</pre>"
        )
    else:
        additions_inner = '<div class="empty-side">No additions.</div>'
    return (
        f'<details class="side removals" open>\n'
        f"  <summary>\n"
        f'    <span class="sv"></span>\n'
        f"    Removals\n"
        f'    <span class="side-badge">−</span>\n'
        f'    <span class="line-count">{deletions} lines</span>\n'
        f"  </summary>\n"
        f"  {removals_inner}\n"
        f"</details>\n"
        f'<details class="side additions" open>\n'
        f"  <summary>\n"
        f'    <span class="sv"></span>\n'
        f"    Additions\n"
        f'    <span class="side-badge">+</span>\n'
        f'    <span class="line-count">{additions} lines</span>\n'
        f"  </summary>\n"
        f"  {additions_inner}\n"
        f"</details>"
    )


def _render_meta(
    branch_name: str,
    base_label: str,
    pre: Resolution,
    post: Resolution,
    all_pre_stats: tuple[int, int, int],
    all_post_stats: tuple[int, int, int],
) -> str:
    pre_files, pre_adds, pre_dels = all_pre_stats
    post_files, post_adds, post_dels = all_post_stats
    return (
        f'<span class="stat">branch <strong>{_safe_html(branch_name)}</strong></span>'
        f'<span class="stat">base <strong>{_safe_html(base_label)}</strong></span>'
        f'<span class="stat">{_safe_html(pre.short)} → '
        f"<strong>{_safe_html(post.short)}</strong></span>"
        f'<span class="stat"><span class="add">+{post_adds}</span> / '
        f'<span class="del">−{post_dels}</span> across '
        f"<strong>{post_files}</strong> files (post)</span>"
        f'<span class="stat">was <span class="add">+{pre_adds}</span> / '
        f'<span class="del">−{pre_dels}</span> across '
        f"<strong>{pre_files}</strong> files (pre)</span>"
    )


def _render_summary_list(all_stats: tuple[int, int, int], commit_count: int) -> str:
    files, additions, deletions = all_stats
    items_html = [
        f"<li><strong>{files}</strong> files changed</li>",
        f'<li><span class="add">+{additions}</span> additions</li>',
        f'<li><span class="del">−{deletions}</span> deletions</li>',
        f"<li><strong>{commit_count}</strong> commits ahead of base</li>",
    ]
    return "\n".join(items_html)


def _render_path_list(all_deltas: list[FileDelta], side: str) -> str:
    if not all_deltas:
        return f'<p class="empty">No files {_safe_html(side)}.</p>'
    items_html = []
    for each_delta in all_deltas:
        if side == rebase_constants.STATUS_LOST_LABEL:
            change_html = (
                f'<span class="add">+{each_delta.pre_additions}</span>'
                f' <span class="del">−{each_delta.pre_deletions}</span>'
            )
        else:
            change_html = (
                f'<span class="add">+{each_delta.post_additions}</span>'
                f' <span class="del">−{each_delta.post_deletions}</span>'
            )
        items_html.append(
            f"<li><code>{_safe_html(each_delta.path)}</code> &nbsp; {change_html}</li>"
        )
    return "<ul>\n" + "\n".join(items_html) + "\n</ul>"


def _render_file_row(
    delta: FileDelta,
    base_ref: str,
    pre_ref: str,
    post_ref: str,
    working_dir: Path,
) -> str:
    badge_text = delta.status
    summary_stat = (
        f'<span class="add">+{delta.post_additions}</span>'
        f' <span class="del">−{delta.post_deletions}</span>'
    )
    pre_line = (
        f'<span class="add">+{delta.pre_additions}</span> /'
        f' <span class="del">−{delta.pre_deletions}</span>'
    )
    post_line = (
        f'<span class="add">+{delta.post_additions}</span> /'
        f' <span class="del">−{delta.post_deletions}</span>'
    )
    if badge_text == rebase_constants.STATUS_LOST_LABEL:
        diff_label = "Pre-rebase patch (lost in this rebase)"
        diff_text = _collect_per_file_diff(base_ref, pre_ref, delta.path, working_dir)
    else:
        diff_label = "Post-rebase patch"
        diff_text = _collect_per_file_diff(base_ref, post_ref, delta.path, working_dir)
    diff_html = _render_split_diff_panels(diff_text)
    return (
        f'<details class="file">\n'
        f"  <summary>\n"
        f'    <span class="chev"></span>\n'
        f'    <span class="path">{_safe_html(delta.path)}</span>\n'
        f'    <span class="badge {badge_text}">{badge_text}</span>\n'
        f'    <span class="stat">{summary_stat}</span>\n'
        f"  </summary>\n"
        f'  <div class="file-body">\n'
        f'    <div class="ba">\n'
        f'      <div class="panel lost">\n'
        f'        <div class="k">Pre-rebase</div>\n'
        f'        <p class="stat-line">{pre_line}</p>\n'
        f"      </div>\n"
        f'      <div class="panel gained">\n'
        f'        <div class="k">Post-rebase</div>\n'
        f'        <p class="stat-line">{post_line}</p>\n'
        f"      </div>\n"
        f"    </div>\n"
        f'    <div class="diff-source">{_safe_html(diff_label)}</div>\n'
        f"    {diff_html}\n"
        f"  </div>\n"
        f"</details>"
    )


def _render_commit_walk(all_rows: list[CommitWalkRow]) -> str:
    if not all_rows:
        return (
            '<p class="empty-section">No commits walked. '
            "Either the pre-rebase and post-rebase tips are identical, "
            "or `git range-diff` returned no parseable rows.</p>"
        )
    label_table = rebase_constants.ALL_STATUS_LABEL_BY_GLYPH
    glyph_table = rebase_constants.ALL_DISPLAY_GLYPH_BY_STATUS
    items_html = []
    for each_row in all_rows:
        css_class, plain_label = label_table.get(
            each_row.status,
            (rebase_constants.FALLBACK_CSS_CLASS, rebase_constants.FALLBACK_STATUS_DESCRIPTION),
        )
        glyph = glyph_table.get(each_row.status, "?")
        pre_marker = (
            f"<code>{_safe_html(each_row.pre_sha)}</code>"
            if each_row.pre_sha and not each_row.pre_sha.startswith(rebase_constants.DASH_SHA_PREFIX)
            else "<em>none</em>"
        )
        post_marker = (
            f"<code>{_safe_html(each_row.post_sha)}</code>"
            if each_row.post_sha
            and not each_row.post_sha.startswith(rebase_constants.DASH_SHA_PREFIX)
            else "<em>none</em>"
        )
        items_html.append(
            f'<div class="item {css_class}">\n'
            f'  <div class="n {css_class}">{glyph}</div>\n'
            f"  <div>\n"
            f'    <div class="t">{_safe_html(each_row.subject) or plain_label}</div>\n'
            f'    <div class="d">{plain_label} · pre: {pre_marker} → post: {post_marker}</div>\n'
            f"  </div>\n"
            f"</div>"
        )
    return "\n".join(items_html)


def _wrap_lede(narrative_text: Optional[str]) -> str:
    if narrative_text is None:
        return ""
    cleaned = narrative_text.strip()
    if not cleaned:
        return ""
    return f'<p class="lede">{cleaned}</p>'


def _wrap_story_bucket(narrative_text: Optional[str]) -> str:
    if narrative_text is None or not narrative_text.strip():
        return (
            '<p class="placeholder">Not supplied. '
            "Pass --whats-new / --whats-gone / --whats-kept.</p>"
        )
    return f"<p>{narrative_text.strip()}</p>"


def render_rebase_html(
    repo_argument: str,
    pre_argument: str,
    post_argument: str,
    base_argument: Optional[str],
    whats_new: Optional[str] = None,
    whats_gone: Optional[str] = None,
    whats_kept: Optional[str] = None,
    why_summary: Optional[str] = None,
    why_gained_lost: Optional[str] = None,
    why_files: Optional[str] = None,
    why_commits: Optional[str] = None,
) -> tuple[str, str, dict[str, int]]:
    """Collect rebase data and render it through the rebase template.

    Args:
        repo_argument: Path to the git repository (resolved relative to cwd).
        pre_argument: Pre-rebase ref (e.g., ORIG_HEAD or a sha).
        post_argument: Post-rebase ref (e.g., HEAD or a sha).
        base_argument: Rebase base ref, or None to auto-detect.

    Returns:
        Tuple of (rendered_html, page_title, summary_counts) where
        summary_counts contains keys: kept, changed, lost, gained,
        files_lost, files_gained, files_other.

    Raises:
        SystemExit: When refs do not resolve, the repo is missing, or
            git invocations fail.
    """
    repo_input = Path(repo_argument).expanduser().resolve()
    if not repo_input.exists():
        raise SystemExit(f"Repo path does not exist: {repo_input}")
    repo_root = _detect_repo_root(repo_input)

    pre = _resolve_required_ref("pre-rebase", pre_argument, repo_root)
    post = _resolve_required_ref("post-rebase", post_argument, repo_root)

    if base_argument is None:
        base_label = _detect_base_ref(post.sha, repo_root)
    else:
        _reject_unsafe_ref(base_argument)
        base_label = base_argument

    base_sha = _resolve_optional_ref(base_label, repo_root)
    if base_sha is None:
        raise SystemExit(f"Cannot resolve base ref: {base_label!r}")
    base_short = _run_git(
        rebase_constants.ALL_GIT_REV_PARSE_SHORT_ARGS, base_sha, working_dir=repo_root
    ).strip()
    base_subject = _run_git(
        rebase_constants.ALL_GIT_LOG_ONE_FORMAT_SUBJECT_ARGS, base_sha, working_dir=repo_root
    ).strip()
    base_resolution = Resolution(
        label=base_label, sha=base_sha, short=base_short, subject=base_subject
    )

    branch_name = _detect_branch_name(repo_root)
    repo_name = repo_root.name

    pre_stats = _parse_shortstat(
        _run_git(
            rebase_constants.ALL_GIT_DIFF_SHORTSTAT_ARGS,
            f"{base_label}...{pre.sha}",
            working_dir=repo_root,
        )
    )
    post_stats = _parse_shortstat(
        _run_git(
            rebase_constants.ALL_GIT_DIFF_SHORTSTAT_ARGS,
            f"{base_label}...{post.sha}",
            working_dir=repo_root,
        )
    )
    pre_commits_count = _count_commits(base_label, pre.sha, repo_root)
    post_commits_count = _count_commits(base_label, post.sha, repo_root)

    pre_files = _collect_numstat(base_label, pre.sha, repo_root)
    post_files = _collect_numstat(base_label, post.sha, repo_root)
    file_deltas = _compose_file_deltas(
        pre_files, post_files, pre.sha, post.sha, repo_root
    )
    lost_deltas = [
        each_delta
        for each_delta in file_deltas
        if each_delta.status == rebase_constants.STATUS_LOST_LABEL
    ]
    gained_deltas = [
        each_delta
        for each_delta in file_deltas
        if each_delta.status == rebase_constants.STATUS_GAINED_LABEL
    ]

    walk_rows = _collect_commit_walk(base_label, pre.sha, post.sha, repo_root)

    page_title = f"Rebase report — {branch_name} → {base_label}"

    file_rows_html = "\n".join(
        _render_file_row(each_delta, base_label, pre.sha, post.sha, repo_root)
        for each_delta in file_deltas
    )
    if not file_rows_html:
        file_rows_html = '<p class="empty-section">No files changed in either side of the rebase.</p>'

    replacements = rebase_constants.make_rebase_template_replacements(
        page_title=_safe_html(page_title),
        eyebrow=_safe_html(f"rebase report · {repo_name}"),
        heading=_safe_html(f"Rebased {branch_name} onto {base_label}"),
        meta=_render_meta(branch_name, base_label, pre, post, pre_stats, post_stats),
        context=(
            f"Pre-rebase ref <code>{_safe_html(pre.label)}</code> "
            f"= <code>{_safe_html(pre.short)}</code> ({_safe_html(pre.subject)}). "
            f"Post-rebase ref <code>{_safe_html(post.label)}</code> "
            f"= <code>{_safe_html(post.short)}</code> ({_safe_html(post.subject)}). "
            f"Base <code>{_safe_html(base_label)}</code> "
            f"= <code>{_safe_html(base_resolution.short)}</code>."
        ),
        whats_new=_wrap_story_bucket(whats_new),
        whats_gone=_wrap_story_bucket(whats_gone),
        whats_kept=_wrap_story_bucket(whats_kept),
        base_label=_safe_html(base_label),
        pre_short=_safe_html(pre.short),
        post_short=_safe_html(post.short),
        pre_summary_list=_render_summary_list(pre_stats, pre_commits_count),
        post_summary_list=_render_summary_list(post_stats, post_commits_count),
        lost_count=str(len(lost_deltas)),
        gained_count=str(len(gained_deltas)),
        lost_block=_render_path_list(lost_deltas, rebase_constants.STATUS_LOST_LABEL),
        gained_block=_render_path_list(gained_deltas, rebase_constants.STATUS_GAINED_LABEL),
        file_rows=file_rows_html,
        commit_walk=_render_commit_walk(walk_rows),
        why_summary=_wrap_lede(why_summary),
        why_gained_lost=_wrap_lede(why_gained_lost),
        why_files=_wrap_lede(why_files),
        why_commits=_wrap_lede(why_commits),
    )

    template_path = (
        Path(__file__).parent.parent / "templates" / "rebase.html.tmpl"
    ).resolve()
    template_text = template_path.read_text(encoding="utf-8")
    rendered = template_text
    for each_key, each_value in replacements.items():
        marker = f"<!-- TPL:{each_key} -->"
        rendered = rendered.replace(marker, each_value)

    summary_counts = {
        "kept": sum(1 for each_row in walk_rows if each_row.status == rebase_constants.STATUS_KEPT),
        "changed": sum(
            1 for each_row in walk_rows if each_row.status == rebase_constants.STATUS_CHANGED
        ),
        "lost": sum(
            1 for each_row in walk_rows if each_row.status == rebase_constants.STATUS_LOST_GLYPH
        ),
        "gained": sum(
            1 for each_row in walk_rows if each_row.status == rebase_constants.STATUS_GAINED_GLYPH
        ),
        "files_lost": len(lost_deltas),
        "files_gained": len(gained_deltas),
        "files_other": len(file_deltas) - len(lost_deltas) - len(gained_deltas),
    }
    return rendered, page_title, summary_counts
