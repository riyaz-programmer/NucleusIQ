"""Tests for @mcp_tool_filter and MCPToolset."""

from __future__ import annotations

import pytest
from nucleusiq_mcp.decorators import MCPToolset, mcp_tool_filter
from nucleusiq_mcp.models import MCPToolSpec


def _spec(name: str) -> MCPToolSpec:
    return MCPToolSpec(name=name)


class TestMCPToolFilterDecorator:
    def test_metadata_attached(self):
        @mcp_tool_filter(name="read_only", description="Only read")
        def f(spec):
            return True

        assert f.filter_name == "read_only"
        assert f.filter_description == "Only read"

    def test_defaults_to_function_name_and_docstring(self):
        @mcp_tool_filter()
        def my_filter(spec):
            """Filter docstring."""
            return True

        assert my_filter.filter_name == "my_filter"
        assert "Filter docstring" in my_filter.filter_description

    def test_predicate_runs(self):
        @mcp_tool_filter()
        def reject_admin(spec):
            return "admin" not in spec.name

        assert reject_admin(_spec("search")) is True
        assert reject_admin(_spec("admin_delete")) is False


class TestMCPToolset:
    def test_all_of_default(self):
        ts = MCPToolset.all_of(
            lambda s: s.name.startswith("get_"),
            lambda s: "x" in s.name,
        )
        assert ts(_spec("get_x")) is True
        assert ts(_spec("get_y")) is False
        assert ts(_spec("set_x")) is False

    def test_any_of(self):
        ts = MCPToolset.any_of(
            lambda s: s.name.startswith("get_"),
            lambda s: s.name.startswith("list_"),
        )
        assert ts(_spec("get_x")) is True
        assert ts(_spec("list_x")) is True
        assert ts(_spec("set_x")) is False

    def test_empty_returns_true(self):
        ts = MCPToolset.all_of()
        assert ts(_spec("anything")) is True
        ts2 = MCPToolset.any_of()
        assert ts2(_spec("anything")) is True

    def test_invalid_mode(self):
        with pytest.raises(ValueError, match="mode"):
            MCPToolset([], mode="bogus")

    def test_repr_lists_filter_names(self):
        @mcp_tool_filter(name="A")
        def a(spec):
            return True

        @mcp_tool_filter(name="B")
        def b(spec):
            return True

        ts = MCPToolset.all_of(a, b)
        r = repr(ts)
        assert "A" in r
        assert "B" in r
        assert "all" in r
