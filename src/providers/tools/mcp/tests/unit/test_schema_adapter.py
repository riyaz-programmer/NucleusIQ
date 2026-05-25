"""Tests for MCPSchemaAdapter."""

from __future__ import annotations

from nucleusiq_mcp.models import MCPToolSpec
from nucleusiq_mcp.schema_adapter import MCPSchemaAdapter


class TestNormalizeInputSchema:
    def test_none_returns_empty_object_schema(self):
        out = MCPSchemaAdapter._normalize_input_schema(None)
        assert out == {"type": "object", "properties": {}, "required": []}

    def test_empty_dict_returns_empty_object_schema(self):
        out = MCPSchemaAdapter._normalize_input_schema({})
        assert out == {"type": "object", "properties": {}, "required": []}

    def test_strips_meta_fields(self):
        s = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "x",
            "title": "MyTool",
            "description": "...",
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        }
        out = MCPSchemaAdapter._normalize_input_schema(s)
        assert "$schema" not in out
        assert "$id" not in out
        assert "title" not in out
        assert "description" not in out
        assert out["properties"] == {"x": {"type": "string"}}

    def test_does_not_mutate_input(self):
        s = {"type": "object", "properties": {"x": {"type": "string"}}}
        snap = dict(s)
        MCPSchemaAdapter._normalize_input_schema(s)
        assert s == snap

    def test_default_required_added(self):
        s = {"type": "object", "properties": {"x": {"type": "string"}}}
        out = MCPSchemaAdapter._normalize_input_schema(s)
        assert out["required"] == []

    def test_preserves_existing_required(self):
        s = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        }
        out = MCPSchemaAdapter._normalize_input_schema(s)
        assert out["required"] == ["x"]

    def test_adds_type_object_if_missing(self):
        out = MCPSchemaAdapter._normalize_input_schema(
            {"properties": {"x": {"type": "string"}}}
        )
        assert out["type"] == "object"

    def test_inlines_defs_ref(self):
        s = {
            "type": "object",
            "properties": {"x": {"$ref": "#/$defs/MyType"}},
            "$defs": {"MyType": {"type": "string", "enum": ["a", "b"]}},
        }
        out = MCPSchemaAdapter._normalize_input_schema(s)
        assert out["properties"]["x"] == {"type": "string", "enum": ["a", "b"]}

    def test_inlines_definitions_ref(self):
        s = {
            "type": "object",
            "properties": {"x": {"$ref": "#/definitions/MyType"}},
            "definitions": {"MyType": {"type": "integer"}},
        }
        out = MCPSchemaAdapter._normalize_input_schema(s)
        assert out["properties"]["x"] == {"type": "integer"}

    def test_unknown_ref_left_alone(self):
        s = {
            "type": "object",
            "properties": {"x": {"$ref": "#/components/schemas/Foo"}},
        }
        out = MCPSchemaAdapter._normalize_input_schema(s)
        # No $defs, so ref is preserved.
        assert out["properties"]["x"]["$ref"].startswith("#/components/")

    def test_ref_with_extra_fields_merges(self):
        s = {
            "type": "object",
            "properties": {"x": {"$ref": "#/$defs/T", "description": "the X"}},
            "$defs": {"T": {"type": "string"}},
        }
        out = MCPSchemaAdapter._normalize_input_schema(s)
        assert out["properties"]["x"]["type"] == "string"
        assert out["properties"]["x"]["description"] == "the X"

    def test_array_items_walked(self):
        s = {
            "type": "object",
            "properties": {"xs": {"type": "array", "items": {"$ref": "#/$defs/I"}}},
            "$defs": {"I": {"type": "string"}},
        }
        out = MCPSchemaAdapter._normalize_input_schema(s)
        assert out["properties"]["xs"]["items"] == {"type": "string"}


class TestToNucleusiqSpec:
    def test_full_spec_built(self):
        spec = MCPToolSpec(
            name="search",
            description="Search the web",
            input_schema={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        )
        out = MCPSchemaAdapter.to_nucleusiq_spec(spec, final_name="search")
        assert out["name"] == "search"
        assert out["description"] == "Search the web"
        assert out["parameters"]["required"] == ["q"]

    def test_renamed_uses_final_name(self):
        spec = MCPToolSpec(name="search", description="d")
        out = MCPSchemaAdapter.to_nucleusiq_spec(spec, final_name="github_search")
        assert out["name"] == "github_search"

    def test_missing_description_falls_back_to_name(self):
        spec = MCPToolSpec(name="search")
        out = MCPSchemaAdapter.to_nucleusiq_spec(spec, final_name="search")
        assert out["description"] == "search"

    def test_missing_input_schema(self):
        spec = MCPToolSpec(name="ping")
        out = MCPSchemaAdapter.to_nucleusiq_spec(spec, final_name="ping")
        assert out["parameters"] == {"type": "object", "properties": {}, "required": []}
