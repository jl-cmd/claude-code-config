# claude-code-config

A Claude Code plugin that enforces consistent development standards across every repo you work in. Install once, get TDD enforcement, code quality hooks, specialized agents, and battle-tested rules everywhere.

## Install

```bash
claude plugin install jl-cmd/claude-code-config
```

That's it. Rules, hooks, agents, commands, and skills activate automatically on next session start.

## What This Solves

Without this plugin, every repo needs its own `.claude/rules/`, `.claude/hooks/`, `.claude/agents/`, etc. That means:

- Duplicated config across 5+ repos
- Drift when you update standards in one place but forget others
- New repos start with zero guardrails

This plugin centralizes all general-purpose Claude Code config. Project-specific rules still live in each repo's `.claude/` directory and merge with these.

## What's Included

### Rules (13)

Behavioral rules loaded into every session. These shape how Claude approaches work before any code is written.

| Rule | What it does |
|------|-------------|
| `tdd` | Red-green-refactor is non-negotiable |
| `code-standards` | References CODE_RULES.md for all code generation |
| `conservative-action` | Research first, act only when explicitly asked |
| `right-sized-engineering` | Simple > clever, functions > classes, concrete > abstract |
| `explore-thoroughly` | Read before proposing, map patterns before committing |
| `research-mode` | Anti-hallucination: cite sources, say "I don't know", use direct quotes |
| `parallel-tools` | Independent tool calls run simultaneously |
| `agent-spawn-protocol` | Context sufficiency check before delegating to agents |
| `git-workflow` | Draft PRs, one commit per review stage, stacked PR patterns |
| `code-reviews` | Systematic PR review response protocol |
| `testing` | Complete mocks, reference TEST_QUALITY.md |
| `context7` | Fetch current docs via Context7 MCP instead of relying on training data |
| `cleanup-temp-files` | Remove scratch files after tasks complete |

### Docs (4)

Reference documents that rules and agents point to for detailed standards.

| Document | Coverage |
|----------|----------|
| `CODE_RULES.md` | Hook-enforced rules, naming conventions, config patterns, type hints, readability rubric |
| `TEST_QUALITY.md` | Test writing standards, mock completeness, assertion patterns |
| `REACT_PATTERNS.md` | Component architecture, hooks, state management conventions |
| `DJANGO_PATTERNS.md` | Model patterns, view architecture, ORM best practices |

### Agents (34)

Specialized agent prompts for common development tasks. Claude Code automatically discovers these and makes them available for delegation.

**Code Quality:** clean-coder, code-quality-agent, code-standards-agent, readability-review-agent, refactoring-specialist, right-sized-engineer

**Testing:** tdd-test-writer, test-data-builder, validation-expert

**Planning:** plan-executor, parallel-workflow-coordinator, mandatory-agent-workflow-agent, stub-detector-agent

**Documentation:** docs-agent, doc-orchestrator, user-docs-writer, project-docs-analyzer

**Configuration:** config-extraction-agent, config-centralizer, magic-value-eliminator-agent, project-structure-organizer-agent

**Tooling:** agent-writer, skill-writer-agent, skill-to-agent-converter, tooling-builder

**Git:** git-commit-crafter, pr-description-writer, session-continuity-manager

**File Formats:** docx-agent, pdf-agent, xlsx-agent

**Other:** clasp-deployment-orchestrator, workflow-visual-documenter, project-context-loader

### Commands (11)

Slash commands for common workflows.

| Command | Purpose |
|---------|---------|
| `/commit` | Structured git commit with conventional format |
| `/plan` | Create implementation plans with config search |
| `/implement` | Execute plans with TDD workflow |
| `/review-plan` | Review and critique implementation plans |
| `/readability-review` | 8-dimension readability scoring |
| `/right-size` | Check for over/under-engineering |
| `/stubcheck` | Find stubs, TODOs, and NotImplementedError |
| `/pr-comments` | Process PR review comments systematically |
| `/docupdate` | Update documentation after changes |
| `/initialize` | Session initialization with protocol review |
| `/sum` | Summarize current work context |

### Skills (13)

| Skill | Purpose |
|-------|---------|
| `prompt-generator` | Write, refine, and structure prompts for Claude with emotion-informed framing |
| `agent-prompt` | Craft structured agent prompts and spawn background agents after approval |
| `tdd-team` | Orchestrate a 4-agent TDD team (planner, tester, implementer, validator) |
| `pr-review-responder` | Systematic PR review response: fetch comments, checklist, fix, reply, commit |
| `anthropic-plan` | Readonly codebase exploration before code changes, produces a plan file |
| `readability-review` | 8-dimension readability scoring (160 pts) with automatic fixes |
| `ingest` | Digest codebase into LLM-friendly text files via gitingest |
| `rule-audit` | Full enforcement audit of rules, hooks, and docs across user and project layers |
| `rule-creator` | Create and harden Claude Code rules with positive framing and rationale |
| `skill-writer` | Guide for creating well-structured Agent Skills |
| `everything-search` | Fast Windows file search via Everything (voidtools) es.exe |
| `recall` | Retrieve prior session context and decisions from Obsidian vault |
| `remember` | Save decisions, gotchas, and architectural choices to Obsidian vault |

### Hooks (18 registered, 70+ files)

Automated enforcement that runs on Claude Code events. All hooks use `python3` and `${CLAUDE_PLUGIN_ROOT}` for cross-platform compatibility.

#### PreToolUse (before tool execution)

| Matcher | Hook | What it does |
|---------|------|-------------|
| Write\|Edit | `write-existing-file-blocker` | Warns before overwriting files that should be edited |
| Write\|Edit | `sensitive-file-protector` | Blocks writes to .env, credentials, and sensitive files |
| Write\|Edit | `pyautogui-scroll-blocker` | Prevents pyautogui scroll direction bugs |
| Write\|Edit | `hook-format-validator` | Validates hook file format on write |
| Write\|Edit | `run_all_validators` | Runs the full validation suite (30+ checks) |
| Edit | `refactor-guard` | Ensures refactoring happens only after green tests |
| Edit | `migration-safety-advisor` | Warns about risky database migration patterns |
| Bash | `destructive-command-blocker` | Blocks rm -rf, git reset --hard, and other destructive commands |
| AskUserQuestion | `attention-needed-notify` | Desktop notification when Claude needs your input |

#### Other Events

| Event | Hook | What it does |
|-------|------|-------------|
| UserPromptSubmit | `hook-structure-context` | Injects hook directory context into session |
| SessionStart (compact) | `compact-context-reinject` | Re-injects critical rules after context compaction |
| SessionStart | `plugin-data-dir-cleanup` | Cleans stale plugin data on session start |
| Stop | `attention-needed-notify` | Desktop notification when Claude stops |
| SessionEnd | `session-end-cleanup` | Cleans temporary state on session end |
| ConfigChange | `config-change-guard` | Guards against accidental settings changes |
| PostToolUse (Write\|Edit) | `mypy_validator` | Runs mypy type checking after file writes |
| PostToolUse (Write\|Edit) | `e2e-test-validator` | Validates e2e test conventions after writes |
| Notification | `claude-notification-handler` | Routes Claude Code notifications to desktop |

#### Validators Module

The `hooks/validators/` directory contains 30+ individual check modules with a full test suite:

Abbreviations, code quality, comments, file structure, git conventions, magic values, mypy integration, PR references, Python antipatterns, Python style, React patterns, ruff integration, security, TODO tracking, type safety, useless test detection, and more.

## Recommended Companion Plugins

These plugins provide additional skills and capabilities that complement this config. Install any that fit your workflow:

```bash
claude plugin install anthropics/claude-code-plugins        # Official: frontend-design, code-review, playwright, hookify, skill-creator, claude-md-management, serena, pyright-lsp, typescript-lsp, claude-code-setup
claude plugin install anthropics/claude-code-workflows      # Official: python-dev, ui-design, unit-testing, context-management, agent-teams, and more
claude plugin install jl-cmd/claude-journal                 # Session logging to Obsidian vault (provides /session-log)
claude plugin install jl-cmd/claude-deep-research           # Deep multi-source research with citations
claude plugin install jl-cmd/claude-workflow                # Workflow definitions with YAML schemas
```

GSD (project management) is available as an npm package:
```bash
npx get-shit-done-cc
```

## Customization

Plugin rules merge with your project's `.claude/` config. To override a plugin rule for a specific project, create a rule with the same filename in your project's `.claude/rules/` directory.

Plugin hooks run alongside any hooks in your project's `settings.json` or `settings.local.json`.

## Requirements

- Claude Code CLI
- Python 3.8+ (for hooks)

## License

MIT
