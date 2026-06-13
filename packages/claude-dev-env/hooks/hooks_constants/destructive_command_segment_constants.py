"""Segment-splitting and command-name constants for the destructive command blocker compound rm guard."""

ALL_SHELL_CONTROL_OPERATOR_TOKENS: frozenset[str] = frozenset({"&&", "||", ";", "|", "&", "\n", "\r"})
ALL_COMMAND_LAUNCHER_WRAPPER_COMMANDS: frozenset[str] = frozenset(
    {
        "timeout",
        "nohup",
        "nice",
        "ionice",
        "stdbuf",
        "time",
        "setsid",
        "chrt",
        "taskset",
    }
)
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
        "awk",
        "gawk",
        "mawk",
        "nawk",
        "make",
        "tclsh",
        "expect",
        "lua",
    }
)
ALL_REMOTE_AND_PROGRAM_STRING_EXECUTORS: frozenset[str] = frozenset(
    {
        "ssh",
        "python",
        "python2",
        "python3",
        "perl",
        "ruby",
        "node",
        "deno",
        "bun",
        "php",
    }
)
ALL_STRING_ARGUMENT_EXECUTION_FLAGS: frozenset[str] = frozenset({"-c", "-e"})
