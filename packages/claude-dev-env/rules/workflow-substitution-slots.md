# Workflow Substitution Slot Rule

In a `.workflow.js` agent-prompt template, every per-call or per-iteration value an agent must fill in is marked with the angle-bracket convention — `<plate.svg>`, `<object.svg>`, `<glow_hex>`, `cand_<i>`. A bare token such as `cand_i` reads as a fixed literal, so an agent can create one literal directory named `cand_i` and overwrite it across every iteration of a loop, collapsing an N-iteration gate into a single run.

When a loop builds a per-iteration path or output key, write the index as a slot — `cand_<i>` — or spell out `replace <i> with the iteration index 0, 1, 2` in the step text. The sibling source template `theme-icon-set/SKILL.md` marks every per-call slot this way.

`workflow_substitution_slot_blocker.py` (PreToolUse on Write/Edit) blocks a `.workflow.js` write whose looped content carries a bare `<word>_<i|j|k>` token as a path or quoted-key segment, and returns the corrective message.
