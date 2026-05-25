"""Tests for the adapter-local domain models."""

from __future__ import annotations

from nucleusiq_mcp.models import MCPContent, MCPToolResult, MCPToolSpec


class TestMCPContent:
    def test_text_content(self):
        c = MCPContent(kind="text", text="hello")
        assert c.kind == "text"
        assert c.text == "hello"
        assert c.data is None

    def test_immutable(self):
        c = MCPContent(kind="text", text="x")
        try:
            c.text = "y"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("MCPContent must be frozen")


class TestMCPToolResult:
    def test_join_text(self):
        r = MCPToolResult(
            content=[
                MCPContent(kind="text", text="hello"),
                MCPContent(kind="text", text="world"),
            ]
        )
        assert r.join_text() == "hello\nworld"

    def test_join_text_custom_sep(self):
        r = MCPToolResult(
            content=[
                MCPContent(kind="text", text="a"),
                MCPContent(kind="text", text="b"),
            ]
        )
        assert r.join_text(sep=" | ") == "a | b"

    def test_join_text_skips_non_text(self):
        r = MCPToolResult(
            content=[
                MCPContent(kind="text", text="hello"),
                MCPContent(kind="image", data="...", mime_type="image/png"),
            ]
        )
        assert r.join_text() == "hello"

    def test_join_text_empty(self):
        assert MCPToolResult().join_text() == ""

    def test_join_text_skips_blank_text(self):
        r = MCPToolResult(
            content=[
                MCPContent(kind="text", text=""),
                MCPContent(kind="text", text="hi"),
            ]
        )
        assert r.join_text() == "hi"

    def test_has_non_text_false(self):
        r = MCPToolResult(content=[MCPContent(kind="text", text="x")])
        assert not r.has_non_text()

    def test_has_non_text_true(self):
        r = MCPToolResult(
            content=[
                MCPContent(kind="text", text="x"),
                MCPContent(kind="image", data="..."),
            ]
        )
        assert r.has_non_text()

    def test_defaults(self):
        r = MCPToolResult()
        assert r.content == []
        assert r.structured is None
        assert r.is_error is False
        assert r.meta is None


class TestMCPToolSpec:
    def test_defaults(self):
        s = MCPToolSpec(name="search")
        assert s.description == ""
        assert s.input_schema == {}
        assert s.output_schema is None
        assert s.title is None
        assert s.annotations is None

    def test_full(self):
        s = MCPToolSpec(
            name="search",
            description="d",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            title="Search",
            annotations={"readOnly": True},
        )
        assert s.title == "Search"
        assert s.annotations == {"readOnly": True}
