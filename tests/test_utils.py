"""Tests for utils."""

from prforge.utils import format_files, parse_json_list, strip_fences, truncate


def test_strip_fences():
    assert strip_fences("```json\n[1,2]\n```") == "[1,2]"


def test_parse_json_list_plain():
    assert parse_json_list('["a.py", "b.py"]') == ["a.py", "b.py"]


def test_parse_json_list_with_prose():
    text = 'Here are the files:\n```json\n["src/x.py"]\n```\nthanks'
    assert parse_json_list(text) == ["src/x.py"]


def test_parse_json_list_empty():
    assert parse_json_list("no json here") == []


def test_truncate():
    assert truncate("abc", 10) == "abc"
    out = truncate("abcdefghij", 5)
    assert out.startswith("abcde") and "truncated" in out


def test_format_files():
    out = format_files({"a.py": "x = 1"})
    assert "FILE: a.py" in out and "x = 1" in out
