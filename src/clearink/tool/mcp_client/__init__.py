"""MCP (Model Context Protocol) client — connect to external tool servers over stdio."""

from .client import MCPClient  # noqa: F401
from .utils import normalize_mcp_name, _load_servers_config  # noqa: F401
from .core import (  # noqa: F401
    assemble_tool_pool,
    connect_mcp,
    _mcp_clients,
    _mcp_lock,
    _make_mcp_handler,
    _register_mcp_tools_for_client,
    _unregister_mcp_tools_for_client,
)
