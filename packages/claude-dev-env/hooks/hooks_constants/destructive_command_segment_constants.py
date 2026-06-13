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
ALL_BENIGN_COMPOUND_SEGMENT_COMMANDS: frozenset[str] = frozenset(
    {
        "echo",
        "printf",
        "gh",
        "head",
        "tail",
        "cat",
        "ls",
        "grep",
        "wc",
        "sort",
        "uniq",
        "true",
        "git",
    }
)
ALL_OUTPUT_REDIRECTION_OPERATORS: frozenset[str] = frozenset({">", ">>", "&>", ">|"})
ALL_READ_ONLY_GIT_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "status",
        "log",
        "show",
        "diff",
        "rev-parse",
        "rev-list",
        "describe",
        "config",
        "remote",
        "fetch",
        "ls-files",
        "ls-remote",
        "ls-tree",
        "cat-file",
        "blame",
        "shortlog",
        "name-rev",
        "for-each-ref",
        "symbolic-ref",
        "merge-base",
        "count-objects",
        "version",
        "help",
    }
)
ALL_READ_ONLY_GH_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "view",
        "list",
        "status",
        "checks",
        "diff",
        "search",
        "browse",
        "api",
    }
)
ALL_READ_ONLY_SUBCOMMANDS_BY_DISPATCHING_PROGRAM: dict[str, frozenset[str]] = {
    "git": ALL_READ_ONLY_GIT_SUBCOMMANDS,
    "gh": ALL_READ_ONLY_GH_SUBCOMMANDS,
}
LAUNCHER_POSITIONAL_VALUE_SHAPE_PATTERN: str = (
    r"^(?:0x[0-9A-Fa-f]+"
    r"|[0-9]+(?:[.,][0-9]+)?[smhd]?"
    r"|[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*)$"
)
ALL_LAUNCHER_OPTIONS_TAKING_SEPARATE_VALUE: frozenset[str] = frozenset(
    {
        "-s",
        "--signal",
        "-k",
        "--kill-after",
        "-n",
    }
)
ALL_SUBSHELL_GROUPING_CHARACTERS: str = "({"
