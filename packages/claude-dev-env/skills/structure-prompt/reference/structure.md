# Structural ordering

The optimized prompt presents blocks in this fixed sequence:

1. Mission block
2. Metadata block
3. Framework block
4. Questions block
5. Output spec block
6. Data body block

## Procedure

1. Extract each tagged block from the input.
2. Concatenate the blocks in the sequence above.
3. Preserve every byte of identifiers, IDs, SHAs, prefixes, file paths, proper names, and code content exactly as supplied.

## Multiple data bodies

When the input contains multiple data body blocks (e.g., several file diffs), group them as a contiguous final section in their original relative order.

## Atomicity

The framework block stays whole. The data body section sits as one contiguous region at the end.
