"""Schema translation between MCP tool definitions and NucleusIQ specs.

The MCP spec uses JSON Schema for tool inputs/outputs, which is mostly
compatible with NucleusIQ's :class:`~nucleusiq.tools.BaseTool` spec
format.  This module handles edge cases:

* Strip JSON Schema dialect / unsupported fields the LLM providers
  often reject (``$id``, ``$schema``, ``$defs``).
* Inline simple ``$ref``s when possible (best-effort).
* Ensure ``type: "object"`` is present at the top level (NucleusIQ
  contract expects this).
* Fall back to an empty object schema if MCP returns nothing.

This module is pure-functional — no I/O, no SDK calls — which makes it
easy to unit-test without any MCP server.
"""

from __future__ import annotations

import copy
from typing import Any

from nucleusiq_mcp.models import MCPToolSpec

__all__ = ["MCPSchemaAdapter"]


# Fields that confuse some LLM providers' tool-spec validators.  Strip
# them silently — they are JSON Schema metadata that does not change
# semantics for function-calling validation.
_STRIP_TOP_LEVEL = frozenset(
    [
        "$schema",
        "$id",
        "title",
        "description",  # top-level description: we keep tool description separately
    ]
)


class MCPSchemaAdapter:
    """Convert :class:`MCPToolSpec` into a NucleusIQ ``get_spec()`` dict.

    Why a class rather than a free function?  Future extension points
    (custom JSON Schema rewriters, per-server validation, name mapping
    policy) belong here without breaking the call site.  OCP-clean.
    """

    @staticmethod
    def to_nucleusiq_spec(tool: MCPToolSpec, *, final_name: str) -> dict[str, Any]:
        """Build the dict returned by :meth:`BaseTool.get_spec`.

        Args:
            tool: The MCP tool advertisement.
            final_name: The (possibly prefixed) name to register in
                NucleusIQ — may differ from ``tool.name`` when
                collision policy kicked in.

        Returns:
            ``{"name": ..., "description": ..., "parameters": <schema>}``
        """
        parameters = MCPSchemaAdapter._normalize_input_schema(tool.input_schema)
        return {
            "name": final_name,
            "description": tool.description or tool.name,
            "parameters": parameters,
        }

    # ------------------------------------------------------------------ #
    # Private helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize_input_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
        """Return a safe, normalized JSON Schema for tool parameters.

        Behaviour:
        * ``None`` / empty → ``{"type": "object", "properties": {}, "required": []}``
        * Removes ``$schema``, ``$id``, top-level ``title``, top-level
          ``description``.
        * Resolves single-level ``$defs`` references when trivial.
        * Ensures ``"type": "object"`` is present.
        """
        if not schema:
            return {"type": "object", "properties": {}, "required": []}

        # Deep-copy so callers' input schema is never mutated.
        s = copy.deepcopy(schema)

        # Strip metadata that some LLM providers reject.
        for key in _STRIP_TOP_LEVEL:
            s.pop(key, None)

        # Inline trivial $ref references (best-effort).
        defs = s.pop("$defs", None) or s.pop("definitions", None)
        if defs and isinstance(defs, dict):
            s = MCPSchemaAdapter._inline_refs(s, defs)

        # Ensure object type for the top-level schema.
        s.setdefault("type", "object")
        if s["type"] == "object":
            s.setdefault("properties", {})
            s.setdefault("required", [])

        return s

    @staticmethod
    def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
        """Walk the schema, replacing ``$ref: "#/$defs/Foo"`` with the def.

        Best-effort: only handles ``"#/$defs/<name>"`` and
        ``"#/definitions/<name>"`` patterns.  Other refs are left
        intact — provider validators will surface them.
        """
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str):
                ref = node["$ref"]
                for prefix in ("#/$defs/", "#/definitions/"):
                    if ref.startswith(prefix):
                        key = ref[len(prefix) :]
                        if key in defs:
                            # Inline the referenced schema in-place.
                            replacement = copy.deepcopy(defs[key])
                            # Merge non-$ref fields from the original node
                            # (e.g. ``description``) onto the replacement.
                            for k, v in node.items():
                                if k != "$ref":
                                    replacement.setdefault(k, v)
                            return MCPSchemaAdapter._inline_refs(replacement, defs)
            # Recurse into nested dicts.
            return {k: MCPSchemaAdapter._inline_refs(v, defs) for k, v in node.items()}
        if isinstance(node, list):
            return [MCPSchemaAdapter._inline_refs(item, defs) for item in node]
        return node
