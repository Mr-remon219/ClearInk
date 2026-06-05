"""MCP client core — global state, tool pool assembly, connect_mcp entry point."""

from __future__ import annotations

import threading
from typing import Any

from clearink.hook import run_hooks
from ..register import register_tool, TOOL, TOOL_HANDLERS
from .utils import (
    _MCP_TOOL_PREFIX,
    normalize_mcp_name,
    _load_servers_config,
    _parse_mcp_tool_name,
)
from .client import MCPClient

# ── Global state ──────────────────────────────────────────

_mcp_clients: dict[str, MCPClient] = {}  # normalized_name → client
_mcp_lock = threading.RLock()

# Track which MCP tool entries are in TOOL/TOOL_HANDLERS so we can
# remove stale ones on reconnect.
_registered_mcp_tool_names: set[str] = set()


# ── MCP tool handler factory ───────────────────────────────

def _make_mcp_handler(server_name: str, tool_name: str):
    """Create a closure that dispatches to the correct MCP client."""

    def handler(**kwargs):
        client = _mcp_clients.get(server_name)
        if client is None:
            return f"Error: MCP server '{server_name}' is not connected"
        return client.call_tool(tool_name, kwargs)

    return handler


# ── Tool pool assembly ────────────────────────────────────

def _register_mcp_tools_for_client(server_name: str, client: MCPClient) -> None:
    """Register all tools from *client* into the global registries."""
    for tool_def in client.tools:
        full_name = tool_def["name"]
        parsed = _parse_mcp_tool_name(full_name)
        if parsed is None:
            continue
        _, original_name = parsed

        handler = _make_mcp_handler(server_name, original_name)

        if full_name not in _registered_mcp_tool_names:
            TOOL.append(tool_def)
            TOOL_HANDLERS[full_name] = handler
            _registered_mcp_tool_names.add(full_name)


def _unregister_mcp_tools_for_client(server_name: str) -> None:
    """Remove all MCP tools belonging to *server_name* from global registries."""
    prefix = f"{_MCP_TOOL_PREFIX}{server_name}__"

    for name in list(TOOL_HANDLERS.keys()):
        if name.startswith(prefix):
            TOOL_HANDLERS.pop(name, None)
            _registered_mcp_tool_names.discard(name)

    for i in range(len(TOOL) - 1, -1, -1):
        if TOOL[i].get("name", "").startswith(prefix):
            TOOL.pop(i)


def assemble_tool_pool() -> tuple[list[dict], dict[str, Any]]:
    """Return the current MCP portion of the tool pool.

    Called each API turn to merge MCP tools with native tools.
    """
    with _mcp_lock:
        tools: list[dict] = []
        handlers: dict[str, Any] = {}

        for server_name, client in _mcp_clients.items():
            if not client.connected:
                continue
            for tool_def in client.tools:
                full_name = tool_def["name"]
                parsed = _parse_mcp_tool_name(full_name)
                if parsed is None:
                    continue
                _, original_name = parsed
                tools.append(tool_def)
                handlers[full_name] = _make_mcp_handler(
                    server_name, original_name,
                )

        return (tools, handlers)


# ── Public: connect_mcp ───────────────────────────────────

def connect_mcp(name: str) -> str:
    """Connect to an MCP server and discover its tools.

    The server must be defined in ``data/mcp/servers.json``.
    """
    config = _load_servers_config()
    if not config:
        return "Error: no MCP servers configured.  Add entries to data/mcp/servers.json"

    norm_name = normalize_mcp_name(name)
    server_config = None
    original_key = None

    for key, cfg in config.items():
        if normalize_mcp_name(key) == norm_name:
            if not cfg.get("enabled", True):
                return f"Error: MCP server '{key}' is disabled (enabled: false)"
            server_config = cfg
            original_key = key
            break

    if server_config is None:
        available = ", ".join(config.keys())
        return (
            f"Error: MCP server '{name}' not found in servers.json. "
            f"Available servers: {available or '(none)'}"
        )

    with _mcp_lock:
        if norm_name in _mcp_clients:
            old_client = _mcp_clients[norm_name]
            _unregister_mcp_tools_for_client(norm_name)
            try:
                old_client.disconnect()
            except Exception:
                pass

        client = MCPClient(norm_name, server_config)

        try:
            client.connect()
        except Exception as e:
            return f"Error: could not connect to MCP server '{name}' — {e}"

        try:
            tools = client.discover_tools()
        except Exception as e:
            client.disconnect()
            return f"Error: could not discover tools on '{name}' — {e}"

        _mcp_clients[norm_name] = client
        _register_mcp_tools_for_client(norm_name, client)

    run_hooks("mcp_connected", {
        "server_name": original_key or name,
        "tool_count": len(tools),
    })

    return (
        f"Connected to MCP server '{original_key or name}' ({len(tools)} tools):\n"
        + "\n".join(f"  - {t['name']}" for t in tools)
    )


# ── Registered tool ───────────────────────────────────────

@register_tool(
    name="connect_mcp",
    description="Connect to an MCP (Model Context Protocol) server and "
                "make its tools available.  The server must be configured "
                "in data/mcp/servers.json before calling this tool.  "
                "Discovered tools are automatically namespaced as "
                "mcp__<server>__<tool>.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Server name as defined in servers.json",
            },
        },
        "required": ["name"],
    },
)
def _tool_connect_mcp(name: str) -> str:
    return connect_mcp(name)
