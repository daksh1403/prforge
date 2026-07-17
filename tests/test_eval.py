"""Tests for the eval harness."""

from pathlib import Path

from prforge.config import Config
from prforge.eval.runner import EvalInstance, load_instances, run_eval, self_test


def _make_repo(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "buggy.py").write_text("def multiply(a, b):\n    return a + b\n")
    (root / "test_buggy.py").write_text(
        "from buggy import multiply\n\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n"
    )
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    return root


def test_load_instances(tmp_path: Path):
    f = tmp_path / "inst.jsonl"
    f.write_text(
        '# comment\n'
        '{"id": "a", "repo": "./x", "issue_title": "t", "issue_body": "b"}\n'
        '\n'
        '{"id": "b", "repo": "https://github.com/o/r.git", "issue_title": "t2", "issue_body": "b2", "is_local": false}\n'
    )
    insts = load_instances(f)
    assert len(insts) == 2
    assert insts[0].id == "a" and insts[0].is_local is True
    assert insts[1].id == "b" and insts[1].is_local is False


def test_eval_instance_from_dict_defaults():
    inst = EvalInstance.from_dict({"id": "x", "repo": "./local"})
    assert inst.is_local is True
    assert inst.verify_command == "python -m pytest -q"


def test_run_eval_resolves_local_bug(tmp_path: Path, monkeypatch):
    import sys
    repo = _make_repo(tmp_path / "repo")
    cfg = Config.from_env()
    cfg.workdir_root = tmp_path / "work"
    cfg.workdir_root.mkdir(parents=True, exist_ok=True)
    inst = EvalInstance(
        id="mult",
        repo=str(repo),
        issue_title="multiply returns sum",
        issue_body="multiply() returns a+b; should return a*b.",
        verify_command=f"{sys.executable} -m pytest -q",
    )
    result = run_eval([inst], cfg, lambda c: _FakeLLM(), log=lambda *a: None)
    assert result["total"] == 1
    assert result["resolved"] == 1
    assert result["resolve_rate"] == 1.0
    assert result["results"][0]["edits_applied"] == 1


def test_self_test(tmp_path: Path):
    cfg = Config.from_env()
    cfg.workdir_root = tmp_path / "work"
    cfg.workdir_root.mkdir(parents=True, exist_ok=True)
    result = self_test(cfg, log=lambda *a: None)
    assert result["resolved"] == 1
    assert result["total"] == 1


from prforge.llm import LLMClient


class _FakeLLM(LLMClient):
    def complete(self, system, messages):
        if "triaging" in system:
            return '["buggy.py"]'
        if "step-by-step plan" in system:
            return "Change multiply to return a * b."
        if "SEARCH/REPLACE" in system:
            return ("buggy.py\n<<<<<<< SEARCH\ndef multiply(a, b):\n    return a + b\n"
                    "=======\ndef multiply(a, b):\n    return a * b\n>>>>>>> REPLACE")
        if "pull request" in system:
            return "TITLE: fix\nBODY:\n- fixed\n\nCloses #1"
        return ""
