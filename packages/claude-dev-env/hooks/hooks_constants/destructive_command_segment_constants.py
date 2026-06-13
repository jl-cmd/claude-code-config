"""Segment-splitting and command-name constants for the destructive command blocker compound rm guard."""

ALL_SHELL_CONTROL_OPERATOR_TOKENS: frozenset[str] = frozenset({"&&", "||", ";", "|", "&"})
ALL_INTERPRETER_AND_WRAPPER_COMMANDS: frozenset[str] = frozenset(
    {
        "sh",
        "bash",
        "zsh",
        "dash",
        "ksh",
        "tcsh",
        "csh",
        "fish",
        "pwsh",
        "powershell",
        "cmd",
        "eval",
        "exec",
        "source",
        "sudo",
        "su",
        "env",
        "xargs",
    }
)
