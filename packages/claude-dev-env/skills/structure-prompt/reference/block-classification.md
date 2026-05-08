# Block classification

Every input prompt decomposes into six block types. Tag each region of the input as exactly one type before applying any spoke rules.

## Block types

**Mission block.** One sentence stating what the agent does. The opening directive of the prompt.

**Metadata block.** Identifiers, SHAs, PR numbers, target paths, ID prefixes, scope flags, mode toggles. Short atomic facts the agent uses as parameters.

**Framework block.** The checklist, sub-bucket list, surface list, category list, or step list the agent processes. Multi-item structures with named entries.

**Questions block.** Cross-cutting questions, synthesis questions, or open questions the agent answers after completing the framework.

**Output spec block.** The format the agent's output takes — totals header, per-item shape, ordering, severity tags, locator format, length cap, lead phrase, closing phrase.

**Data body block.** Any of:
- Fenced code block (triple backtick)
- Diff, file dump, transcript, log, table, or document inlined as content
- Any single content region exceeding 500 characters that the agent inspects rather than acts on

## Tagging procedure

1. Read the input prompt top to bottom.
2. Annotate each region with exactly one tag.
3. Confirm every region carries one tag.
4. Proceed to the matching spoke.
