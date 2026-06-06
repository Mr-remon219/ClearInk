from __future__ import annotations

import pytest


class FakeMCPClient:
    instances: list["FakeMCPClient"] = []

    def __init__(self, name: str, config: dict) -> None:
        self.name = name
        self.config = config
        self.tools: list[dict] = []
        self.connected = False
        self.disconnected = False
        FakeMCPClient.instances.append(self)

    def connect(self) -> None:
        if self.config.get("connect_error"):
            raise RuntimeError(self.config["connect_error"])
        self.connected = True

    def discover_tools(self) -> list[dict]:
        if self.config.get("discover_error"):
            raise RuntimeError(self.config["discover_error"])
        self.tools = list(self.config.get("tools", []))
        return self.tools

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        return f"{self.name}:{tool_name}:{arguments}"

    def disconnect(self) -> None:
        self.connected = False
        self.disconnected = True


@pytest.fixture
def isolated_mcp(monkeypatch):
    import clearink.tool.mcp_client.core as core
    import clearink.tool.register as register_mod

    original_tools = list(register_mod.TOOL)
    original_handlers = dict(register_mod.TOOL_HANDLERS)
    original_clients = dict(core._mcp_clients)
    original_registered = set(core._registered_mcp_tool_names)
    FakeMCPClient.instances.clear()

    monkeypatch.setattr(core, "MCPClient", FakeMCPClient)

    yield core

    for client in core._mcp_clients.values():
        try:
            client.disconnect()
        except Exception:
            pass
    register_mod.TOOL[:] = original_tools
    register_mod.TOOL_HANDLERS.clear()
    register_mod.TOOL_HANDLERS.update(original_handlers)
    core._mcp_clients.clear()
    core._mcp_clients.update(original_clients)
    core._registered_mcp_tool_names.clear()
    core._registered_mcp_tool_names.update(original_registered)


def test_connect_mcp_registers_tools_and_dispatches_handler(
    isolated_mcp,
    monkeypatch,
) -> None:
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        isolated_mcp,
        "_load_servers_config",
        lambda: {
            "DeepSeek Search": {
                "tools": [{
                    "name": "mcp__deepseek_search__find",
                    "description": "[MCP] find",
                    "input_schema": {"type": "object", "properties": {}},
                }],
            },
        },
    )
    monkeypatch.setattr(
        isolated_mcp,
        "run_hooks",
        lambda hook_type, context: events.append((hook_type, context)),
    )

    result = isolated_mcp.connect_mcp("deepseek search")

    assert "Connected to MCP server 'DeepSeek Search' (1 tools)" in result
    assert "mcp__deepseek_search__find" in isolated_mcp.TOOL_HANDLERS
    tools, handlers = isolated_mcp.assemble_tool_pool()
    assert [tool["name"] for tool in tools] == ["mcp__deepseek_search__find"]
    assert handlers["mcp__deepseek_search__find"](query="paper") == (
        "deepseek_search:find:{'query': 'paper'}"
    )
    assert events == [
        ("mcp_connected", {"server_name": "DeepSeek Search", "tool_count": 1}),
    ]


def test_connect_mcp_reconnect_cleans_stale_tools(
    isolated_mcp,
    monkeypatch,
) -> None:
    configs = [
        {
            "DeepSeek Search": {
                "tools": [{
                    "name": "mcp__deepseek_search__old",
                    "description": "old",
                    "input_schema": {"type": "object", "properties": {}},
                }],
            },
        },
        {
            "DeepSeek Search": {
                "tools": [{
                    "name": "mcp__deepseek_search__new",
                    "description": "new",
                    "input_schema": {"type": "object", "properties": {}},
                }],
            },
        },
    ]

    monkeypatch.setattr(isolated_mcp, "_load_servers_config", lambda: configs.pop(0))
    monkeypatch.setattr(isolated_mcp, "run_hooks", lambda *_args, **_kwargs: None)

    isolated_mcp.connect_mcp("DeepSeek Search")
    isolated_mcp.connect_mcp("DeepSeek Search")

    assert "mcp__deepseek_search__old" not in isolated_mcp.TOOL_HANDLERS
    assert "mcp__deepseek_search__new" in isolated_mcp.TOOL_HANDLERS
    assert FakeMCPClient.instances[0].disconnected is True


def test_connect_mcp_reports_missing_disabled_and_failed_servers(
    isolated_mcp,
    monkeypatch,
) -> None:
    monkeypatch.setattr(isolated_mcp, "_load_servers_config", lambda: {})
    assert "no MCP servers configured" in isolated_mcp.connect_mcp("any")

    monkeypatch.setattr(
        isolated_mcp,
        "_load_servers_config",
        lambda: {"Disabled": {"enabled": False}},
    )
    assert "is disabled" in isolated_mcp.connect_mcp("disabled")

    monkeypatch.setattr(
        isolated_mcp,
        "_load_servers_config",
        lambda: {"Broken": {"connect_error": "boom"}},
    )
    assert "could not connect" in isolated_mcp.connect_mcp("broken")


def test_mcp_handler_reports_disconnected_server(isolated_mcp) -> None:
    handler = isolated_mcp._make_mcp_handler("missing_server", "find")

    assert handler(query="x") == "Error: MCP server 'missing_server' is not connected"


def test_main_tool_merge_deduplicates_mcp_tools() -> None:
    from clearink.main import _merge_tool_defs

    native = [
        {"name": "read_file", "description": "native"},
        {"name": "mcp__server__find", "description": "already registered"},
    ]
    discovered = [
        {"name": "mcp__server__find", "description": "discovered duplicate"},
        {"name": "mcp__server__cite", "description": "new"},
    ]

    merged = _merge_tool_defs(native, discovered)

    assert [tool["name"] for tool in merged] == [
        "read_file",
        "mcp__server__find",
        "mcp__server__cite",
    ]
    assert merged[1]["description"] == "already registered"
