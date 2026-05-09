# Criteria Reference — Violations and Fixes

Concrete examples for each of the 16 completion criteria. Load this file when a criterion is unclear or when self-auditing.

## Contents

- [1. Typing strictness](#1-typing-strictness)
- [2. Error handling](#2-error-handling)
- [3. Test coverage](#3-test-coverage)
- [4. Dependency injection](#4-dependency-injection)
- [5. Codebase standards](#5-codebase-standards)
- [6. TypedDict protocol](#6-typeddict-protocol)
- [7. Redis boundary](#7-redis-boundary)
- [8. TOML boundary](#8-toml-boundary)
- [9. JSON recursive types](#9-json-recursive-types)
- [10. ASGI / framework boundaries](#10-asgi--framework-boundaries)
- [11. Dynamic import pattern](#11-dynamic-import-pattern)
- [12. Documentation](#12-documentation)
- [13. Build infrastructure](#13-build-infrastructure)
- [14. Lint gates](#14-lint-gates)
- [15. Protocol signature match](#15-protocol-signature-match)
- [16. Auth, credentials, multi-tenancy](#16-auth-credentials-multi-tenancy)

---

## 1. Typing strictness

**What it checks:** Zero `Any`, `object`, `cast()`, `type: ignore`, `noqa`, `.pyi`, stubs, or shims. Mypy strict exits 0.

### Violation

```python
from typing import Any

def load_raw(path: str) -> Any:  # Any return
    with open(path) as f:
        return f.read()  # type: ignore  # untyped blocker
```

### Fix

```python
def load_raw(path: str) -> str:
    with open(path) as file_handle:
        return file_handle.read()
```

### Adversarial probes

- Search for `Any` with `grep -r ": Any" src/ tests/ scripts/`
- Search for `cast(` with `grep -r "cast(" src/ tests/ scripts/`
- Run `mypy --strict src/ tests/ scripts/`

---

## 2. Error handling

**What it checks:** No `try`/`except` in core logic that recovers or softens. Failures propagate.

### Violation

```python
def load_config(path: str) -> AppConfig:
    try:
        raw = toml.load(path)
        return _decode_app_config(raw)
    except Exception:
        return DEFAULT_CONFIG  # swallowed, caller never knows
```

### Fix

```python
def load_config(path: str) -> AppConfig:
    raw = toml.load(path)
    return _decode_app_config(raw)
```

Caller handles `FileNotFoundError` or `ValidationError` at the edge.

### Adversarial probes

- Search for `except Exception` in `src/` (not `tests/`)
- Search for `except:` bare excepts
- Verify every `try` block either re-raises or is at a system boundary

---

## 3. Test coverage

**What it checks:** 100% statement and branch coverage. Zero mocks. Zero weak assertions. Zero fake tests.

### Violation (weak assertion)

```python
def test_load_config():
    config = load_config("test.toml")
    assert config is not None  # doesn't check any field
```

### Violation (mock)

```python
def test_fetch(mocker):
    mocker.patch("redis.Redis.get", return_value=b"value")
    result = fetch_from_cache("key")
    assert result == b"value"  # tested a mock, not Redis
```

### Fix (real assertion)

```python
def test_load_config(tmp_path):
    config_path = tmp_path / "test.toml"
    config_path.write_text('[app]\nname = "test"\nport = 8080\n')
    config = load_config(str(config_path))
    assert config["name"] == "test"
    assert config["port"] == 8080
```

### Adversarial probes

- `pytest --cov=src --cov=scripts --cov-report=term-missing`
- Check for `mocker`, `unittest.mock`, `MagicMock` in tests
- Check for `assert x is not None` — flag as weak

---

## 4. Dependency injection

**What it checks:** `Services/` modules have `_test_hooks.py`. `Libs/testing.py` exports utilities. No `if`/`else` test-vs-prod branching.

### Violation (conditional)

```python
def get_db():
    if IS_TEST:  # branching on test mode
        return FakeDB()
    return RealDB(os.environ["DB_URL"])
```

### Fix (hook)

```python
# Services/users/_test_hooks.py
_db_factory: Callable[[], Database] = lambda: RealDB(os.environ["DB_URL"])

# Production: hook is set at import time (no change needed)
# Test:
# from Services.users._test_hooks import _db_factory
# _db_factory = lambda: FakeDB()

def get_db() -> Database:
    return _db_factory()
```

### Adversarial probes

- Every `Services/*/` directory must contain `_test_hooks.py`
- Search for `IS_TEST`, `if.*test` in `src/`
- Search for `Fake`, `Mock` in `src/` (should only appear in tests)

---

## 5. Codebase standards

**What it checks:** DRY (no duplicate functions >3 lines), no dead code, no fallbacks, no shims, no `TypeAlias`, no `TYPE_CHECKING`.

### Violation (duplicate)

```python
# In auth.py
def validate_email(address: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, address))

# In users.py — same 4 lines, different file
def check_email_format(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))
```

### Fix

Extract to a shared module. One definition. Import it.

### Adversarial probes

- `grep -r "TYPE_CHECKING" src/ tests/ scripts/` — must be zero
- `grep -r "TypeAlias" src/ tests/ scripts/` — must be zero
- Read function bodies >3 lines, compare pairwise for duplication

---

## 6. TypedDict protocol

**What it checks:** Every TypedDict has `_encode_*` and `_decode_*`. Decode calls `require_*` on every field.

### Violation (missing validation)

```python
class AppConfig(TypedDict):
    name: str
    port: int

def _decode_app_config(raw: dict[str, object]) -> AppConfig:
    return AppConfig(
        name=raw["name"],      # no type check — raw["name"] could be int
        port=raw["port"],      # no range check — port could be -1
    )
```

### Fix

```python
def _decode_app_config(raw: dict[str, object]) -> AppConfig:
    name = require_str(raw, "name")
    port = require_int_range(raw, "port", min_value=1, max_value=65535)
    return AppConfig(name=name, port=port)
```

### Adversarial probes

- Every TypedDict in `src/` must have a corresponding `_decode_*` function
- Every `_decode_*` must call `require_*` for each field
- Missing field, wrong type, out-of-range → must raise, not coerce

---

## 7. Redis boundary

**What it checks:** No `Redis[Any]` in annotations. Use helpers or Protocol.

### Violation

```python
from redis.asyncio import Redis

async def cache_get(client: Redis[Any], key: str) -> bytes | None:
    return await client.get(key)
```

### Fix

```python
from typing import Protocol

class CacheReader(Protocol):
    async def get(self, key: str) -> bytes | None: ...

async def cache_get(client: CacheReader, key: str) -> bytes | None:
    return await client.get(key)
```

### Adversarial probes

- `grep -r "Redis\[" src/` — must be zero
- `grep -r "Redis\[Any\]" src/` — must be zero (redundant check)

---

## 8. TOML boundary

**What it checks:** No `TYPE_CHECKING` for TOML. Untyped dict → TypedDict conversion before use.

### Violation

```python
def load_config(path: str) -> dict[str, Any]:  # untyped dict escapes
    return toml.load(path)
```

### Fix

```python
def load_config(path: str) -> AppConfig:
    raw: dict[str, object] = toml.load(path)
    return _decode_app_config(raw)  # TypedDict leaves this function
```

### Adversarial probes

- Search for `toml.load` — verify the return value is immediately decoded into a TypedDict
- Never return a raw `dict` from a function whose name implies typed output

---

## 9. JSON recursive types

**What it checks:** No Pydantic. Manual `json.loads()` → TypeAlias → `_decode_*`.

### Violation

```python
from pydantic import BaseModel

class TreeNode(BaseModel):
    value: str
    children: list["TreeNode"]
```

### Fix

```python
import json

JsonNode: TypeAlias = dict[str, "JsonNode | str"]

def load_tree(path: str) -> TreeNode:
    with open(path) as fh:
        raw: JsonNode = json.loads(fh.read())
    return _decode_tree_node(raw)
```

### Adversarial probes

- `grep -r "pydantic" src/` — must be zero
- `grep -r "BaseModel" src/` — must be zero

---

## 10. ASGI / framework boundaries

**What it checks:** Protocol for minimal interface. No `dict[str, Any]` in ASGI scopes. Parse at edge.

### Violation

```python
async def app(scope: dict[str, Any], receive, send):
    body = await receive()
    ...
```

### Fix

```python
class ASGIScope(Protocol):
    type: str
    method: str
    path: str
    headers: list[tuple[bytes, bytes]]

class ASGIReceive(Protocol):
    async def __call__(self) -> dict[str, bytes | bool]: ...

async def app(scope: ASGIScope, receive: ASGIReceive, send) -> None:
    ...
```

### Adversarial probes

- Search for `dict[str, Any]` in function signatures in `src/`
- Every ASGI handler must define Protocols, not inline dict access

---

## 11. Dynamic import pattern

**What it checks:** `importlib.import_module()` + `getattr()` annotated with Protocol type. No `Any` leaks.

### Violation

```python
mod = importlib.import_module("plugins.my_plugin")
plugin = getattr(mod, "MyPlugin")  # type is Any
plugin.run()  # unchecked
```

### Fix

```python
mod = importlib.import_module("plugins.my_plugin")
cls = getattr(mod, "MyPlugin")
plugin: PluginProtocol = cls()  # annotation overrides Any
plugin.run()
```

### Adversarial probes

- Search for `getattr(` — every result must have a Protocol annotation on the same line or next line
- Verify the Protocol has the method being called

---

## 12. Documentation

**What it checks:** Google-style docstrings on every public function, method, class. `Args:`, `Returns:`, `Raises:`.

### Violation

```python
def process(items):
    # process the items
    return [x * 2 for x in items]
```

### Fix

```python
def double_each(items: list[int]) -> list[int]:
    """Return a new list with each element doubled.

    Args:
        items: Input integers.

    Returns:
        A new list of doubled values.

    Raises:
        TypeError: If any element is not an integer (caught by type checker).
    """
    return [each_item * 2 for each_item in items]
```

### Adversarial probes

- Every `def` in a module without `_` prefix must have a docstring with Args/Returns/Raises
- Docstring first line must be a single concise sentence

---

## 13. Build infrastructure

**What it checks:** `Makefile`, `pyproject.toml`, `scripts/guard.py` exist with correct content.

### Violation

Missing `scripts/guard.py`. `pyproject.toml` has no `[tool.mypy]` section.

### Fix

Create each file with the required content. See sibling repos for templates.

### Adversarial probes

- `test -f Makefile && grep -q "^check:" Makefile`
- `test -f pyproject.toml && grep -q "\[tool.mypy\]" pyproject.toml`
- `test -f scripts/guard.py`

---

## 14. Lint gates

**What it checks:** `make lint` runs mypy (strict) + ruff + guard. All cover `src/`, `tests/`, `scripts/`. Lint exits 0 before test is valid.

### Violation

Running `make test` before `make lint`. Or `make lint` passes but mypy wasn't in strict mode.

### Fix

`make lint` target must include `mypy --strict src/ tests/ scripts/`. `make test` should depend on `lint` in the Makefile.

### Adversarial probes

- `grep "strict" pyproject.toml` — must find `strict = true` under `[tool.mypy]`
- `make lint` must complete before `make test` in the session

---

## 15. Protocol signature match

**What it checks:** Protocol signatures match the real API. API change → Protocol breaks at type-check time.

### Violation

```python
class CacheClient(Protocol):
    async def get(self, key: str) -> str | None: ...  # returns str

# Real Redis returns bytes, not str — Protocol is wrong
```

### Fix

```python
class CacheClient(Protocol):
    async def get(self, key: str) -> bytes | None: ...
```

### Adversarial probes

- Compare every Protocol method signature against the real implementation's signature
- Change the real API, run mypy, verify the Protocol line fails

---

## 16. Auth, credentials, multi-tenancy

**What it checks:** Explicit, typed auth. Typed connection factories. MCP resources follow same strictness.

### Violation

```python
def get_connection(tenant: str) -> Connection:
    dsn = f"postgresql://user:pass@host/{tenant}"  # string-formatted
    return connect(dsn)
```

### Fix

```python
class TenantConnectionFactory(Protocol):
    def __call__(self, tenant_id: TenantId) -> Database: ...

def get_connection(tenant_factory: TenantConnectionFactory, tenant_id: TenantId) -> Database:
    return tenant_factory(tenant_id)
```

### Adversarial probes

- `grep -r "f\"postgresql" src/` — must be zero
- `grep -r "f\"mysql" src/` — must be zero
- Every DB connection path must go through a typed factory
