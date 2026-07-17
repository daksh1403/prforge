"""Tests for the MCP server (skipped if `mcp` is not installed)."""

import pytest

try:
    import mcp  # noqa: F401
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


@pytest.mark.skipif(not HAS_MCP, reason="mcp package not installed")
def test_mcp_server_registers_tools():
    from prforge.mcp_server import _make_server

    mcp = _make_server()
    # FastMCP exposes registered tools via _tool_manager
    tools = mcp._tool_manager._tools if hasattr(mcp, "_tool_manager") else {}
    names = set(tools.keys()) if isinstance(tools, dict) else {t.name for t in tools}
    assert "fetch_issue" in names
    assert "solve_issue" in names
    assert "get_diff" in names
