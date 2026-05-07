    """Reviewer specifications.

    A ReviewerSpec carries the two knobs that vary across the bugbot, copilot, and
    claude reviewers: the case-insensitive substring used to match the reviewer's
    GitHub login, and the callable that classifies a single review payload as
    ``"clean"`` or ``"dirty"``. The spec instances declared at module scope are
    imported by test files via the entry-point wrapper modules.
    """