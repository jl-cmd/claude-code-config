---
name: structure-prompt
description: Restructure any user-provided prompt so the framework precedes the data body, persona framing becomes a task constraint, multi-category audits emit explicit per-category dispositions, and ceremony directives become measurable constraints. Trigger when the user invokes /structure-prompt, pastes a prompt and asks to optimize it, asks for a "minimally invasive edit" to a prompt artifact, or asks to "tighten this prompt".
---

# structure-prompt

One pass per invocation. Classify each block of the input prompt, apply the matching spoke rules, and emit the rewritten prompt as a single fenced block.

## Pre-flight

The input prompt arrives as the user's message body or as a fenced block within it. Treat the entire input as the artifact under optimization.

## First invocation of a session

Read [`reference/block-classification.md`](reference/block-classification.md), then [`reference/output-contract.md`](reference/output-contract.md).

## Match situation, read spoke

| Situation | Read |
|---|---|
| Starting any optimization | [`reference/block-classification.md`](reference/block-classification.md) |
| Input contains a fenced code block, diff, dump, transcript, or single content region ≥ 500 characters | [`reference/structure.md`](reference/structure.md) |
| Input opens with a role assignment ("You are…", "Act as…", "Imagine you are…", "As a…") | [`reference/persona.md`](reference/persona.md) |
| Input names 2+ categories, surfaces, sub-buckets, items, checks, or criteria the agent processes | [`reference/per-category.md`](reference/per-category.md) |
| Input contains performance directives ("be thorough", "think step by step", "you are an expert", "please", "kindly") | [`reference/directives.md`](reference/directives.md) |
| Input contains narrative directives ("try to", "look at", "make sure", "consider", "be sure to") | [`reference/constraints.md`](reference/constraints.md) |
| Input has typos, mixed bullet styles, untagged code blocks, or whitespace runs | [`reference/cleanup.md`](reference/cleanup.md) |
| Tick is ambiguous against the spokes above | [`reference/examples.md`](reference/examples.md) |
| Emitting the rewritten prompt | [`reference/output-contract.md`](reference/output-contract.md) |

## Folder map

- `SKILL.md` — this hub.
- `reference/` — rule detail per situation.
