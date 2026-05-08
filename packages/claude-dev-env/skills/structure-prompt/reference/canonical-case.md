# Mark the canonical sub-bucket with ⭐

When a framework has many sub-buckets, one of them usually carries the category's signature failure mode. Marking that sub-bucket with ⭐ helps the auditing agent give it extra attention.

## Detection

The marker fires when ALL three hold:

- The framework has 5 or more sub-buckets
- No sub-bucket already carries the ⭐ marker
- Either the sibling rubric names a canonical example, or one sub-bucket clearly has more concrete content than the others

## How to pick the canonical sub-bucket

In order:

1. **Rubric match.** When the sibling rubric (`../category_rubrics/<name>.md`) describes a "Canonical example" or names one axis as the signature pattern, pick that sub-bucket.
2. **Bullet density.** When the rubric stays silent, count the concrete bullets per sub-bucket. The sub-bucket with the most bullets that cite a real identifier or line number wins.
3. **Identifier density.** When two sub-buckets tie on bullet count, pick the one whose identifiers appear most often in the data body.

## How to mark it

Append `⭐ canonical <category-letter> case` after the sub-bucket title, on the same line.

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

When research turns up no clear canonical case (the bullets are evenly weighted, no rubric guidance, no identifier-density signal), the marker pass stays silent. The framework reads fine without one; better to leave it unmarked than to pick arbitrarily.
