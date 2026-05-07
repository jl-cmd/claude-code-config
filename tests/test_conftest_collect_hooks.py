            / "test_code_rules_gate.py"
```
should match since `test_code_rules_gate.py` is a surviving test file. Conversely, the pattern
```python
conftest_collect_paths.append(
    repository_root / "test_code_rules_gate.py"
)
```