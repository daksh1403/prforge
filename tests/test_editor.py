"""Tests for the SEARCH/REPLACE editor."""

from pathlib import Path

from prforge.tools.editor import apply_edit, parse_edits


def test_parse_single_block():
    text = """src/app.py
<<<<<<< SEARCH
def add(a, b):
    return a + b
=======
def add(a, b):
    return a - b
>>>>>>> REPLACE
"""
    edits = parse_edits(text)
    assert len(edits) == 1
    assert edits[0].filename == "src/app.py"
    assert "return a + b" in edits[0].search
    assert "return a - b" in edits[0].replace


def test_parse_multiple_blocks():
    text = """a.py
<<<<<<< SEARCH
x = 1
=======
x = 2
>>>>>>> REPLACE
b.py
<<<<<<< SEARCH
y = 3
=======
y = 4
>>>>>>> REPLACE
"""
    edits = parse_edits(text)
    assert len(edits) == 2
    assert edits[0].filename == "a.py"
    assert edits[1].filename == "b.py"


def test_apply_edit_replaces(tmp_path: Path):
    f = tmp_path / "f.py"
    f.write_text("def add(a, b):\n    return a + b\n")
    apply_edit(f, "return a + b", "return a - b")
    assert "return a - b" in f.read_text()
    assert "return a + b" not in f.read_text()


def test_apply_edit_missing_search_raises(tmp_path: Path):
    from prforge.tools.editor import EditError

    f = tmp_path / "f.py"
    f.write_text("print('hi')\n")
    try:
        apply_edit(f, "not present", "x")
        assert False, "should have raised"
    except EditError:
        pass
