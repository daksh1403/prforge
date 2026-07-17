"""Tests for codebase helpers."""

from pathlib import Path

from prforge.tools.codebase import build_repo_map, detect_test_command, read_file


def test_build_repo_map_lists_files(tmp_path: Path):
    (tmp_path / "a.py").write_text("print('a')\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "skip.js").write_text("x\n")
    (tmp_path / "b.md").write_text("# hi\n")
    m = build_repo_map(str(tmp_path))
    assert "a.py" in m
    assert "b.md" in m
    assert "node_modules" not in m


def test_detect_test_command_pytest(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    assert detect_test_command(str(tmp_path)) == "pytest -q"


def test_detect_test_command_none(tmp_path: Path):
    assert detect_test_command(str(tmp_path)) is None


def test_read_file(tmp_path: Path):
    (tmp_path / "f.txt").write_text("hello\n")
    assert read_file(str(tmp_path), "f.txt") == "hello\n"
