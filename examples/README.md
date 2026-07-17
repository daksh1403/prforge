# PRForge — Example Issues

Try PRForge on small, well-defined issues first. Good starter targets:

| Repo | Why |
|------|-----|
| your own test repo | safest — you control the result |
| small Python utilities (e.g. `httpie/cli`, `typer`) | clear test suites |
| repos with `good first issue` labels | scoped, beginner-friendly |

## A safe dry run

```bash
# 1. fetch only (no LLM, no writes)
prforge fetch https://github.com/owner/repo/issues/12

# 2. full solve, dry run (writes a local clone + diff, NO push, NO PR)
prforge solve https://github.com/owner/repo/issues/12 --dry-run

# 3. inspect the generated diff
prforge diff https://github.com/owner/repo/issues/12
```

## Going live

```bash
prforge solve https://github.com/owner/repo/issues/12 --no-dry-run
# review the diff in the prompt -> type y -> PR opens
```

## A tiny self-test repo

Create a repo with a deliberate bug and an issue describing it, then point
PRForge at it. Example `buggy.py`:

```python
def multiply(a, b):
    return a + b  # bug: should be a * b
```

And a test `test_buggy.py`:

```python
from buggy import multiply

def test_multiply():
    assert multiply(3, 4) == 12
```

Open an issue titled "multiply returns the sum instead of the product", then:

```bash
prforge solve https://github.com/you/buggy-repo/issues/1 --dry-run
```
