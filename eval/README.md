# PRForge Eval Harness

SWE-bench-style evaluation. Measures the **resolve rate**: the fraction of
instances whose tests pass after the agent applies its patch.

## Quick self-test (no API key, no network)

```bash
prforge eval --self-test
```

Creates a tiny buggy repo, runs the full agent loop with a deterministic fake
LLM, and reports `1/1 resolved`. Verifies the harness itself works.

## Real SWE-bench-lite evaluation

`eval/instances.jsonl` ships with **5 real SWE-bench-lite instances** (astropy).
Each is fully runnable: the runner checks out the `base_commit`, lets the agent
write a fix, applies the gold `test_patch`, then runs the `FAIL_TO_PASS` +
`PASS_TO_PASS` tests.

```bash
prforge eval eval/instances.jsonl
```

> These are large repos — each instance clones a specific commit and runs an
> LLM, so a full run takes time + API budget. Start with 1-2 instances.

## Instance format

```json
{"id": "astropy__astropy-12907",
 "repo": "https://github.com/astropy/astropy.git",
 "issue_title": "astropy__astropy-12907",
 "issue_body": "<problem_statement>",
 "is_local": false,
 "base_commit": "<sha>",
 "test_patch": "<unified diff of gold tests>",
 "fail_to_pass": ["tests/test_x.py::test_y"],
 "pass_to_pass": ["tests/test_z.py::test_w"],
 "agent_test_command": null}
```

| Field | Meaning |
|-------|---------|
| `base_commit` | commit to checkout (shallow fetch by SHA) |
| `test_patch` | gold test diff applied after the agent's fix |
| `fail_to_pass` | tests that must pass after the fix |
| `pass_to_pass` | tests that must keep passing |
| `agent_test_command` | tests the agent runs during its loop (`null` = skip) |

## How resolve is computed

`resolved = (gold test_patch applies cleanly) AND (all fail_to_pass + pass_to_pass tests pass)`

## Faithfulness note

This is a lightweight harness, not the official `swe-bench` package (which uses
per-instance conda envs). For most Python repos `python -m pytest <tests>` from
the repo root works; repos needing special setup can set `verify_command`
explicitly. Extend `run_instance` in `src/prforge/eval/runner.py` for full fidelity.
