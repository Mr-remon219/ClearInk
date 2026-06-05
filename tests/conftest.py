"""Shared pytest fixtures for ClearInk integration tests.

Global state management is the most important concern — ClearInk uses many
module-level mutable globals (TOOL registry, HOOKS, mode state, caches, …)
and tests must leave them exactly as they found them.

Autouse fixtures ensure isolation without each test having to remember to
request the right fixture.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════
# Deep-copy helpers (avoid circular imports from tests.helpers)
# ═══════════════════════════════════════════════════════════════

def _deepcopy(obj):
    return copy.deepcopy(obj)


# ═══════════════════════════════════════════════════════════════
# 1. Global state snapshot + restore (runs BEFORE & AFTER every test)
# ═══════════════════════════════════════════════════════════════

# Modules whose globals we snapshot.  Lazy-imported so conftest
# doesn't trigger tool registration side effects at collect time.

_STATEFUL_MODULES: dict[str, dict[str, list[str]]] = {
    "clearink.tool.register": {
        "attrs": ["TOOL", "TOOL_HANDLERS"],
    },
    "clearink.hook.hook": {
        "attrs": ["HOOKS", "hook_context"],
    },
    "clearink.tool.todo.core": {
        "attrs": ["CURRENT_TODOS"],
    },
    "clearink.user.mode": {
        "attrs": ["_current_mode", "_step_mode"],
    },
    "clearink.system_prompt.system_build": {
        "attrs": ["_last_key", "_last_context", "_last_prompt", "_current_memories"],
    },
}

# Extra globals that need resetting but live on instances / non-module objects
_EXTRA_STATEFUL = [
    "clearink.tool.background.core.background_tasks",
    "clearink.tool.background.core.background_results",
    "clearink.tool.background.core._bg_counter",
    "clearink.tool.mcp_client.core._mcp_clients",
    "clearink.tool.mcp_client.core._registered_mcp_tool_names",
    "clearink.tool.skill.core._skill.AVAILABLE_SKILLS",
    "clearink.tool.scheduler.core.scheduled_jobs",
    "clearink.tool.scheduler.core._agent_busy",
    "clearink.tool.scheduler.core._agent_loop_fn",
    "clearink.tool.task_system.manager._manager._tasks",
    "clearink.tool.team.lifecycle._active_teammates",
    "clearink.tool.team.bus._bus._inbox_dir",
    "clearink.tool.team.protocol.state.pending_requests",
    "clearink.tool.team.protocol.state._request_counter",
    "clearink.api.session._session_manager._sessions",
]


def _import_or_none(module_name: str):
    try:
        return sys.modules.get(module_name)
    except Exception:
        return None


def _resolve_attr(root, attr_chain: str):
    """Walk *attr_chain* (dot-separated) from *root* module/object."""
    obj = root
    for part in attr_chain.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def _patch_cached_path(monkeypatch, module_name: str, attr: str, new_path: Path):
    """Monkeypatch a module-level path attribute if the module is already imported."""
    mod = sys.modules.get(module_name)
    if mod is not None:
        monkeypatch.setattr(mod, attr, new_path)


@pytest.fixture
def reset_global_state():
    """Snapshot & restore all known ClearInk global state around each test.

    This is ``autouse`` so every test gets isolation for free.
    """
    # ── Snapshot before test ────────────────────────────────
    snapshots: dict = {}

    for mod_name, info in _STATEFUL_MODULES.items():
        mod = _import_or_none(mod_name)
        if mod is None:
            continue
        for attr in info["attrs"]:
            val = getattr(mod, attr, None)
            snapshots[(mod_name, attr)] = _deepcopy(val)

    # Extra globals (may live on instances or nested objects)
    for path in _EXTRA_STATEFUL:
        parts = path.rsplit(".", 1)
        mod = _import_or_none(parts[0])
        if mod is None:
            continue
        if len(parts) == 2:
            val = _resolve_attr(mod, parts[1])
        else:
            val = None
        snapshots[path] = _deepcopy(val)

    # ── Yield to test ───────────────────────────────────────
    yield

    # ── Restore after test ──────────────────────────────────
    for mod_name, info in _STATEFUL_MODULES.items():
        mod = _import_or_none(mod_name)
        if mod is None:
            continue
        for attr in info["attrs"]:
            key = (mod_name, attr)
            if key in snapshots:
                setattr(mod, attr, snapshots[key])

    # Restore extra globals
    for path in _EXTRA_STATEFUL:
        parts = path.rsplit(".", 1)
        mod = _import_or_none(parts[0])
        if mod is None:
            continue
        if len(parts) == 2 and path in snapshots:
            # Resolve parent object chain
            attr_parts = parts[1].split(".")
            obj = mod
            for ap in attr_parts[:-1]:
                obj = getattr(obj, ap, None)
                if obj is None:
                    break
            if obj is not None and snapshots[path] is not None:
                try:
                    setattr(obj, attr_parts[-1], snapshots[path])
                except Exception:
                    pass  # some attrs may be read-only


# ═══════════════════════════════════════════════════════════════
# 2. Temporary data directory
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a complete temporary ``data/`` tree and redirect config paths.

    Directory layout created::

        {tmp_path}/data/
          environment/.env
          system_prompts/
            base.md
            guidelines.md
            mode1.md
            mode2.md
            .memory/
              MEMORY.md
          skills/
            google_scholar/
              SKILL.md
          .tasks/
          mcp/
            servers.json
          logs/

    All ``clearink.config`` path constants are monkeypatched to point
    into this tree.
    """
    data = tmp_path / "data"

    # Create directory structure
    (data / "environment").mkdir(parents=True)
    (data / "system_prompts" / ".memory").mkdir(parents=True)
    (data / "skills" / "google_scholar").mkdir(parents=True)
    (data / ".tasks").mkdir(parents=True)
    (data / "mcp").mkdir(parents=True)
    (data / "logs").mkdir(parents=True)

    # .env with minimal config
    (data / "environment" / ".env").write_text(
        "ANTHROPIC_API_KEY=sk-test-key\n"
        "ANTHROPIC_BASE_URL=https://api.example.com\n"
        "MODEL=test-model\n"
        "THINKING_TYPE=disabled\n",
        encoding="utf-8",
    )

    # System prompt stubs
    (data / "system_prompts" / "base.md").write_text(
        "You are ClearInk, a test assistant.", encoding="utf-8"
    )
    (data / "system_prompts" / "guidelines.md").write_text(
        "=== Test Guidelines ===\nBe precise.", encoding="utf-8"
    )
    (data / "system_prompts" / "mode1.md").write_text(
        "Mode 1: Formula Analysis test mode.", encoding="utf-8"
    )
    (data / "system_prompts" / "mode2.md").write_text(
        "Mode 2: Paper Q&A test mode.", encoding="utf-8"
    )
    (data / "system_prompts" / ".memory" / "MEMORY.md").write_text(
        "# Test Memory Index\n", encoding="utf-8"
    )

    # Skill stub
    (data / "skills" / "google_scholar" / "SKILL.md").write_text(
        "---\nname: google_scholar\ndescription: Search Google Scholar\n---\n\n"
        "# Google Scholar Skill\n\nTest skill content.\n",
        encoding="utf-8",
    )

    # MCP config stub
    (data / "mcp" / "servers.json").write_text("{}", encoding="utf-8")

    # ── Monkeypatch config paths ────────────────────────────
    import clearink.config as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", data)
    monkeypatch.setattr(cfg, "ENV_PATH", data / "environment" / ".env")
    monkeypatch.setattr(cfg, "SYSTEM_PROMPTS_DIR", data / "system_prompts")
    monkeypatch.setattr(cfg, "SKILLS_DIR", data / "skills")
    monkeypatch.setattr(cfg, "MEMORY_DIR", data / "system_prompts" / ".memory")
    monkeypatch.setattr(cfg, "TASKS_DIR", data / ".tasks")
    monkeypatch.setattr(cfg, "WORKTREES_DIR", data / ".tasks" / ".worktrees")
    monkeypatch.setattr(cfg, "TASK_OUTPUTS_DIR", data / "task_outputs")
    monkeypatch.setattr(cfg, "TRANSCRIPTS_DIR", data / ".transcripts")
    monkeypatch.setattr(cfg, "LOGS_DIR", data / "logs")
    monkeypatch.setattr(cfg, "TEAM_DIR", data / "team")
    monkeypatch.setattr(cfg, "SCHEDULED_TASKS_DIR", data / ".scheduled_tasks")
    monkeypatch.setattr(cfg, "MCP_CONFIG_PATH", data / "mcp" / "servers.json")

    return data


# ═══════════════════════════════════════════════════════════════
# 3. Mock Anthropic client
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def mock_anthropic(mocker):
    """Mock ``anthropic.Anthropic.messages.create`` to return a configurable response.

    Returns the mock so tests can set ``.return_value`` or ``.side_effect``.
    Default return value: end_turn with "Hello from mock."
    """
    from tests.helpers import make_text_block, make_mock_response

    default = make_mock_response("end_turn", [make_text_block("Hello from mock.")])

    # Manually build the mock chain so autospec doesn't break nested attrs
    mock_instance = mocker.MagicMock()
    mock_instance.messages.create.return_value = default
    mocker.patch("anthropic.Anthropic", return_value=mock_instance)

    # Also mock the module-level _get_client in main.py
    mocker.patch("clearink.main._get_client", return_value=mock_instance)

    return mock_instance.messages.create


# ═══════════════════════════════════════════════════════════════
# 4. Prevent import-time side effects
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _suppress_dotenv(monkeypatch: pytest.MonkeyPatch):
    """Prevent load_dotenv from reading the real .env during test collection/run."""
    try:
        import dotenv
        monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: None)
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch):
    """Ensure test environment variables are set for any subprocess / inline code."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("THINKING_TYPE", "disabled")
