# Copilot Gap Analysis

Categories that Copilot consistently catches but bugteam's audit rubric
(A-J) does not surface.

## Category 1: Log Message Accuracy

Copilot detects when log messages describe behavior the code does not
actually implement (e.g., "moved to Trash" when code marks read-and-keep).
Bugteam's category F (silent failures) does not cover this case.

**Mitigation:** Pre-Copilot lint pass includes log-accuracy as a dedicated
check.

## Category 2: Over-Engineered Patterns

Copilot flags unnecessary abstractions, premature generalization, and
patterns that add complexity without proportional benefit.

**Mitigation:** Right-sized engineering review before Copilot request.

## Category 3: Eager Default Evaluation

Copilot detects `dict.get(key, expensive_default())` and similar patterns
where the default always evaluates regardless of whether the key exists.

**Mitigation:** Pre-Copilot lint pass includes eager-default evaluation
check.

## Planned Rubric Extensions

- Add "log message accuracy" to category F
- Add "over-engineering" as a new sub-category under J
- Add "eager evaluation" under F (silent resource waste)
