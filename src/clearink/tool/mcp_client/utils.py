"""MCP client utilities — constants, name helpers, config loading, schema conversion.

Shared by both ``client.py`` (MCPClient) and ``core.py`` (tool pool /
connect_mcp) to avoid a circular dependency.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ...config import MCP_CONFIG_PATH

# ── Constants ─────────────────────────────────────────────

_MCP_TOOL_PREFIX = "mcp__"
_ILLEGAL_NAME_RE = re.compile(r"[^a-z0-9_]")


# ── Name normalisation ────────────────────────────────────

def normalize_mcp_name(name: str) -> str:
    """Normalize a server name into a safe tool-name prefix."""
    if not name:
        return ""
    name = name.lower()
    name = _ILLEGAL_NAME_RE.sub("_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")
    return name


# ── Config loading ────────────────────────────────────────

def _load_servers_config() -> dict[str, dict]:
    """Load the servers.json configuration file."""
    if not MCP_CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, dict) and not k.startswith("_")}
    except (json.JSONDecodeError, OSError):
        return {}


# ── Tool name helpers ─────────────────────────────────────

def _mcp_tool_name(server_name: str, tool_name: str) -> str:
    """Build a namespaced tool name: ``mcp__<server>__<tool>``"""
    return f"{_MCP_TOOL_PREFIX}{server_name}__{tool_name}"


def _parse_mcp_tool_name(full_name: str) -> tuple[str, str] | None:
    """Parse a namespaced name back to (server_name, original_tool_name)."""
    if not full_name.startswith(_MCP_TOOL_PREFIX):
        return None
    inner = full_name[len(_MCP_TOOL_PREFIX):]
    parts = inner.split("__", 1)
    if len(parts) != 2:
        return None
    return (parts[0], parts[1])


# ── MCP to Anthropic schema conversion ────────────────────

def _convert_json_schema_to_anthropic(prop_schema: dict) -> dict:
    """Convert a JSON Schema property dict to Anthropic input_schema format."""
    schema: dict[str, Any] = {"type": "object", "properties": {}}
    required: list[str] = []

    props = prop_schema.get("properties", {})
    if isinstance(props, dict):
        for name, prop in props.items():
            if not isinstance(prop, dict):
                continue
            entry: dict[str, Any] = {}
            if "type" in prop:
                entry["type"] = prop["type"]
            if "description" in prop:
                entry["description"] = prop["description"]
            if "enum" in prop:
                entry["enum"] = prop["enum"]
            schema["properties"][name] = entry

    req_list = prop_schema.get("required", [])
    if isinstance(req_list, list):
        required = [r for r in req_list if isinstance(r, str)]

    if required:
        schema["required"] = required

    return schema
