"""SWE-bench-style evaluation harness for PRForge."""

from __future__ import annotations

from prforge.eval.runner import (
    EvalInstance,
    load_instances,
    run_eval,
    self_test,
)

__all__ = ["EvalInstance", "load_instances", "run_eval", "self_test"]
