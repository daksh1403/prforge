"""Tests for GitHub URL parsing (no network)."""

import pytest

from prforge.tools.github import parse_issue_url


def test_parse_issue_url_basic():
    owner, repo, number = parse_issue_url("https://github.com/owner/repo/issues/42")
    assert (owner, repo, number) == ("owner", "repo", 42)


def test_parse_issue_url_with_query():
    owner, repo, number = parse_issue_url(
        "https://github.com/owner/repo/issues/7?ref=foo"
    )
    assert (owner, repo, number) == ("owner", "repo", 7)


def test_parse_issue_url_invalid():
    with pytest.raises(ValueError):
        parse_issue_url("https://example.com/foo")
