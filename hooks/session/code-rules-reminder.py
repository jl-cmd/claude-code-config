#!/usr/bin/env python3
"""
UserPromptSubmit hook that detects code-related requests and injects CODE_RULES.md reminder.
Triggers on keywords indicating code writing, planning, or implementation.
"""

import json
import re
import sys

CODE_KEYWORDS = [
    # Creation verbs
    r'\b(write|create|implement|add|build|make|generate|develop|setup|scaffold|bootstrap|initialize|init|compose|construct|define|declare|register|wire|connect|integrate|introduce)\b',
    # Code nouns
    r'\b(code|function|class|method|script|module|component|hook|test|spec|api|endpoint|route|handler|service|util|helper|factory|interface|type|enum|constant|variable|parameter|argument|logic|algorithm|feature|library|package|dependency|plugin|extension|widget|element|node|token|parser|serializer|validator|formatter|linter|compiler|transpiler|bundler|loader|resolver|provider|consumer|producer|subscriber|publisher|emitter|dispatcher|reducer|selector|adapter|wrapper|decorator|mixin|trait|protocol|abstract|generic|iterator|generator|coroutine|fiber|thread|process|worker|job|task|queue|stack|buffer|stream|pipe|socket|channel|signal|slot|observer|mediator|strategy|command|visitor|singleton|repository|gateway|mapper|transformer|converter|encoder|decoder|interceptor|guard|filter|middleware|pipeline|chain|proxy|facade|bridge|flyweight|memento|prototype)\b',
    # Modification verbs
    r'\b(fix|update|refactor|modify|change|edit|rewrite|improve|enhance|optimize|debug|patch|correct|adjust|tweak|rework|revise|extend|expand|rename|move|extract|inline|split|merge|combine|consolidate|simplify|clean|cleanup|reorganize|restructure|decouple|encapsulate|abstract|generalize|specialize|upgrade|downgrade|migrate|convert|transform|adapt|port|backport)\b',
    # Deletion/removal verbs
    r'\b(delete|remove|drop|deprecate|disable|deactivate|unregister|detach|disconnect|unbind|unsubscribe|uninstall|prune|trim|strip|purge|clear|reset|destroy|dispose|release|free|deallocate)\b',
    # Planning verbs
    r'\b(plan|design|structure|architect|outline|draft|sketch|propose|suggest|approach|strategy|solution|how would|how should|how do|how can|how to|what if|where should|when should|why does|why is|could we|should we|can we|let.s|need to|want to|going to)\b',
    # Review/analysis verbs
    r'\b(review|check|analyze|audit|inspect|examine|validate|verify|assess|evaluate|trace|profile|benchmark|measure|monitor|diagnose|troubleshoot|investigate|identify|detect|discover|locate|find the bug|root cause)\b',
    # Testing verbs
    r'\b(test|run tests|unit test|integration test|e2e test|end.to.end|assert|expect|mock|stub|spy|fake|fixture|setup|teardown|arrange|act|coverage|regression|smoke test|snapshot|parameterize)\b',
    # File types
    r'\.(py|js|ts|tsx|jsx|css|scss|less|html|json|yaml|yml|toml|ini|cfg|sql|sh|bash|zsh|vue|svelte|go|rs|java|kt|swift|rb|php|c|cpp|h|hpp|cs|fs|ex|exs|erl|hs|ml|clj|scala|groovy|dart|lua|r|jl|nim|zig|wasm|graphql|proto|tf|hcl)\b',
    # Programming concepts
    r'\b(loop|condition|if statement|switch|try|catch|exception|error handling|async|await|promise|callback|event|listener|state|props|render|return|import|export|inherit|extend|override|decorator|middleware|migration|schema|model|view|controller|template|query|mutation|subscription|context|scope|closure|binding|reference|pointer|memory|allocation|garbage collection|concurrency|parallelism|synchronization|deadlock|race condition|mutex|semaphore|lock|atomic|transaction|rollback|commit|index|constraint|foreign key|primary key|join|aggregate|subquery|cursor|trigger|stored procedure|materialized view)\b',
    # DevOps/infrastructure
    r'\b(deploy|release|publish|ship|rollout|rollback|ci|cd|pipeline|docker|container|kubernetes|k8s|terraform|ansible|nginx|apache|server|cluster|replica|shard|partition|load balancer|proxy|cdn|ssl|tls|certificate|dns|domain|cors|csp|firewall|vpc|subnet|security group|iam|role|policy|secret|vault|env var|environment variable|configuration|config file|dotenv)\b',
    # Database/data
    r'\b(database|db|sql|nosql|mongo|postgres|mysql|sqlite|redis|elasticsearch|dynamodb|cassandra|orm|queryset|recordset|dataset|dataframe|csv|parquet|avro|protobuf|graphql|rest|grpc|websocket|sse|webhook|polling|pagination|cursor|offset|limit|batch|bulk|upsert|crud)\b',
    # Sample/example requests
    r'\b(example|sample|snippet|demo|prototype|proof of concept|poc|skeleton|boilerplate|starter|template|scaffold|seed|initial|baseline|reference implementation|minimal|basic|simple|quick|small)\b',
    # Common tool/framework references
    r'\b(django|flask|fastapi|express|next|react|vue|angular|svelte|tailwind|bootstrap|jest|pytest|mocha|cypress|playwright|selenium|webpack|vite|rollup|esbuild|npm|yarn|pnpm|pip|poetry|cargo|gradle|maven|cmake|bazel|make|dockerfile|compose|github|gitlab|bitbucket|jira|confluence)\b',
]

CONDENSED_RULES = """
<code-rules-reminder>
## MANDATORY CODE RULES - APPLY TO ALL CODE (samples, plans, implementations)

1. **NO COMMENTS** - Self-documenting names only
   - BAD: `d = 0.5  # delay` -> GOOD: `delay_between_retries_seconds = 0.5`

2. **NO MAGIC VALUES** - Everything named and in config
   - BAD: `if score > 0.8:` -> GOOD: `if score > MINIMUM_CONFIDENCE_THRESHOLD:`

3. **NO ABBREVIATIONS** - Full words always
   - BAD: `ctx`, `cfg`, `msg`, `btn` -> GOOD: `context`, `configuration`, `message`, `button`

4. **COMPLETE TYPE HINTS** - All parameters and returns typed, no `Any`

5. **CENTRALIZED CONFIG** - Constants in config/, imported everywhere

6. **SEARCH BEFORE CREATE** - Use everything-search skill before defining constants

7. **ALL IMPORTS SHOWN** - Every code block includes its imports

8. **SELF-CONTAINED COMPONENTS** - Components own their modals/toasts/state

CHECKLIST before writing ANY code:
[ ] No comments (names explain everything)
[ ] No magic values (all named constants)
[ ] No abbreviations (full words)
[ ] Complete types (all params + returns)
[ ] Imports shown

SCOPE: These rules apply to code you WRITE or MODIFY. Do NOT fix violations in untouched code unless explicitly instructed.
</code-rules-reminder>
"""


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    prompt = hook_input.get("prompt", "")

    if not prompt:
        sys.exit(0)

    message_lower = prompt.lower()

    for pattern in CODE_KEYWORDS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            print(CONDENSED_RULES)
            sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
