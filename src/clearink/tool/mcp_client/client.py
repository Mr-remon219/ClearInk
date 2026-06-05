"""MCPClient — stdio JSON-RPC session for a single MCP server.

Uses a background asyncio event loop in a daemon thread to keep the
MCP session alive across multiple synchronous tool calls.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any


class MCPClient:
    """Stdio JSON-RPC client for a single MCP server.

    Spawns a daemon thread with its own asyncio event loop.
    Synchronous ``connect`` / ``discover_tools`` / ``call_tool``
    calls dispatch to the loop via ``run_coroutine_threadsafe``
    and block on a ``threading.Event`` for the result.

    Attributes:
        name:        Normalised server name.
        config:      Raw config dict from servers.json.
        tools:       List of Anthropic-format tool definitions.
        tool_handlers: Dict mapping namespaced tool name → callable.
    """

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
        self.tools: list[dict] = []
        self.tool_handlers: dict[str, Any] = {}

        self._connected = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: Any = None  # ClientSession, alive in the event loop

        # Result bridge: sync callers block on _ready while the async
        # task sets _result / _error.
        self._ready = threading.Event()
        self._result: Any = None
        self._error: Exception | None = None

    # ── Public API ─────────────────────────────────────────

    def connect(self) -> None:
        """Start the event-loop thread and perform the MCP handshake."""
        command = self.config.get("command", "")
        args = self.config.get("args", [])
        env = self.config.get("env", {}) or {}

        if not command:
            raise ValueError(f"MCP server '{self.name}': command is empty")

        merged_env = {**os.environ, **env}

        # Start the event loop in a daemon thread
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(command, args, merged_env),
            daemon=True,
        )
        self._thread.start()

        # Wait for the handshake to complete (or fail)
        self._thread.join(timeout=15)
        if not self._connected:
            raise RuntimeError(
                f"MCP server '{self.name}' handshake timed out or failed"
            )
        if self._error is not None:
            raise self._error

    def discover_tools(self) -> list[dict]:
        """Call ``tools/list`` and convert results to Anthropic format."""
        result = self._dispatch(self._session.list_tools())
        tools = result.tools if hasattr(result, "tools") else result

        converted = []
        from .utils import _mcp_tool_name, _convert_json_schema_to_anthropic

        for tool in tools:
            full_name = _mcp_tool_name(self.name, tool.name)
            input_schema = _convert_json_schema_to_anthropic(
                tool.inputSchema if hasattr(tool, "inputSchema") else {}
            )
            desc = getattr(tool, "description", "") or ""
            if desc:
                desc = f"[MCP:{self.name}] {desc}"
            converted.append({
                "name": full_name,
                "description": desc,
                "input_schema": input_schema,
            })

        self.tools = converted
        return converted

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Invoke an MCP tool and return its text content."""
        if not self._connected:
            return f"Error: MCP server '{self.name}' is not connected"

        try:
            result = self._dispatch(
                self._session.call_tool(tool_name, arguments)
            )
            texts = []
            for block in result.content:
                if hasattr(block, "text"):
                    texts.append(block.text)
                elif hasattr(block, "json"):
                    texts.append(json.dumps(block.json, ensure_ascii=False))
                else:
                    texts.append(str(block))
            return "\n".join(texts) if texts else "(empty result)"
        except Exception as e:
            return f"Error: MCP tool '{tool_name}' failed — {e}"

    def disconnect(self) -> None:
        """Signal the event loop to stop and join the thread."""
        self._connected = False
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._session = None
        self._loop = None
        self._thread = None

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Internal ───────────────────────────────────────────

    def _run_loop(self, command: str, args: list[str], env: dict) -> None:
        """Entry point for the daemon thread.  Runs the event loop
        with the MCP session alive inside it."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(
                self._session_lifecycle(command, args, env)
            )
        except Exception as e:
            self._error = e
        finally:
            self._loop.close()

    async def _session_lifecycle(
        self, command: str, args: list[str], env: dict
    ) -> None:
        """The full async lifecycle: open transport → initialize → wait."""
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.session import ClientSession

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                self._session = session
                try:
                    await session.initialize()
                    self._connected = True
                except Exception as e:
                    self._error = RuntimeError(
                        f"MCP server '{self.name}' handshake failed: {e}"
                    )
                    return

                # Session is now alive — block until disconnect
                while self._connected:
                    await asyncio.sleep(0.5)

    def _dispatch(self, coro) -> Any:
        """Run a coroutine on the event-loop thread and block for the result."""
        if self._loop is None:
            raise RuntimeError("Event loop not started")

        self._ready.clear()
        self._result = None
        self._error = None

        async def _wrapper():
            try:
                self._result = await coro
            except Exception as e:
                self._error = e
            finally:
                self._ready.set()

        asyncio.run_coroutine_threadsafe(_wrapper(), self._loop)
        self._ready.wait(timeout=30)

        if self._error is not None:
            raise self._error
        return self._result
