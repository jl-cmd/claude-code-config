# Mark the canonical sub-bucket with ⭐

When a framework has many sub-buckets, one of them usually carries the category's signature failure mode. Marking that sub-bucket with ⭐ helps the auditing agent give it extra attention.

## Detection

The marker fires when ALL three hold:

- The framework has 5 or more sub-buckets
- No sub-bucket already carries the ⭐ marker
- Either the sibling rubric names a canonical example, or one sub-bucket clearly has more concrete content than the others

## How to pick the canonical sub-bucket

In order:

1. **Rubric match.** When the calling framework provides a sibling rubric (e.g., at `../category_rubrics/<name>.md` in audit-rubric layouts) and that rubric describes a "Canonical example" or names one axis as the signature pattern, pick that sub-bucket. When no sibling rubric exists, skip this step and fall through to bullet density.
2. **Bullet density.** When the rubric stays silent, count the concrete bullets per sub-bucket. The sub-bucket with the most bullets that cite a real identifier or line number wins.
3. **Identifier density.** When two sub-buckets tie on bullet count, pick the one whose identifiers appear most often in the data body.

## How to mark it

Append `⭐ canonical <category-letter> case` after the sub-bucket title, on the same line.

Derive `<category-letter>` from the leading letter of the sub-bucket id (`K3` → `K`, `A2` → `A`, `B1` → `B`). When the framework uses non-lettered sub-bucket ids or no ids at all (e.g., bullets titled `Surface 1`, `Item 1`, `Check 1`), drop the letter and write `⭐ canonical case`.

Example before:
```
**K3. Primary path vs fallback path**
- The file's `if resolved_skill_path is not None:` branch (line 121) is the PRIMARY path…
```

Example after:
```
**K3. Primary path vs fallback path** ⭐ canonical K case
- The file's `if resolved_skill_path is not None:` branch (line 121) is the PRIMARY path…
```

## What stays put

When a ⭐ marker already lives somewhere in the framework, the marker pass leaves it alone — the prompt's author already chose. The skill marks at most one sub-bucket per invocation.

When research turns up no clear canonical case (the bullets are evenly weighted, no rubric guidance, no identifier-density signal), the marker pass leaves the framework unmarked AND MUST emit a gap note via the paste-mode or file-path-mode gap-report mechanism that [`output-contract.md`](output-contract.md) defines for the active emission mode. The framework reads fine without an arbitrary pick, but the deferral itself is recorded — see the [no silent no-op](output-contract.md#disposition-invariants) invariant.
