"""Tests for batch mode."""

from pathlib import Path

from prforge.batch import load_issue_urls


def test_load_issue_urls(tmp_path: Path):
    f = tmp_path / "issues.txt"
    f.write_text(
        "# my issues\n"
        "https://github.com/o/r/issues/1\n"
        "\n"
        "https://github.com/o/r/issues/2\n"
    )
    urls = load_issue_urls(f)
    assert urls == ["https://github.com/o/r/issues/1", "https://github.com/o/r/issues/2"]


def test_load_issue_urls_ignores_comments(tmp_path: Path):
    f = tmp_path / "issues.txt"
    f.write_text("# header\nhttps://github.com/o/r/issues/5\n")
    assert load_issue_urls(f) == ["https://github.com/o/r/issues/5"]
