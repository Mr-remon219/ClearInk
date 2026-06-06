"""Integration tests for the tool registration and cross-tool pipeline.

Covers:
  - Tool registration (register.py)
  - Built-in tools (basetool/): run_bash, read_file, glob
  - Background tasks (background/): submit, collect, query
  - DAG task system (task_system/): create, claim, complete with dependencies
  - Cron scheduler (scheduler/): schedule, list, cancel
  - Flat TODO (todo/): merge vs replace
  - Skill loader (skill/): load existing and missing skills
  - Sub-agent (subagent/): registration verification
  - Team and MCP tools: registration verification
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════
# 1. Tool registration
# ═══════════════════════════════════════════════════════════════


def test_all_tools_registered_after_import():
    """After importing clearink.main, verify all expected tool names exist."""
    import clearink.main  # noqa: F401 — triggers @register_tool side effects

    from clearink.tool.register import TOOL

    registered_names = {t["name"] for t in TOOL}

    expected = {
        # basetool
        "run_bash",
        "read_file",
        "glob",
        # subagent
        "spawn_subagent",
        # task_system
        "create_task",
        "claim_task",
        "complete_task",
        "get_task",
        "list_tasks",
        "check_task",
        "get_unblocked_tasks",
        "auto_dispatch",
        # mcp_client
        "connect_mcp",
        # team
        "spawn_teammate",
        "send_to_teammate",
        "list_teammates",
        "stop_teammate",
        "request_shutdown",
        "assign_task_to_teammate",
        "execute_parallel",
        # regulation
        "regulate_teammates",
        "inspect_teammate",
        "reject_and_reassign",
        "audit_stranded_tasks",
    }

    missing = expected - registered_names
    assert not missing, f"Expected tools not registered: {missing}"

    # Also verify at least the minimum core tools are present
    for core in ("run_bash", "read_file", "glob", "create_task"):
        assert core in registered_names, f"Core tool {core!r} missing from TOOL registry"


def test_duplicate_registration_raises():
    """Registering a tool with a name already in TOOL_HANDLERS raises ValueError."""
    from clearink.tool.register import register_tool, TOOL_HANDLERS

    # Pick a name that is unlikely to collide with existing registrations
    unique_name = "_test_dup_check_tool"

    @register_tool(
        name=unique_name,
        description="Temporary tool for duplicate check",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    def _first_registration() -> str:
        return "first"

    # Verify it was registered
    assert unique_name in TOOL_HANDLERS, "Tool should be in handlers after first registration"

    # Now try registering the same name again — must raise ValueError
    with pytest.raises(ValueError, match="Duplicate tool registration"):
        @register_tool(
            name=unique_name,
            description="Duplicate attempt",
            input_schema={"type": "object", "properties": {}, "required": []},
        )
        def _duplicate() -> str:
            return "duplicate"


# ═══════════════════════════════════════════════════════════════
# 2. Built-in tools (basetool)
# ═══════════════════════════════════════════════════════════════


def test_bash_execution():
    """run_bash executes a simple echo command and returns the output."""
    import clearink.main  # noqa: F401
    from clearink.tool.basetool import run_bash

    result = run_bash(command="echo hello")

    assert "hello" in result, f"Expected 'hello' in output, got: {result}"


def test_read_file(tmp_path: Path):
    """read_file returns file content with line numbers."""
    import clearink.main  # noqa: F401
    from clearink.tool.basetool import read_file

    file_path = tmp_path / "sample.txt"
    file_path.write_text("line one\nline two\nline three\n", encoding="utf-8")

    result = read_file(file_path=str(file_path))

    assert "1\tline one" in result, f"Expected line 1 content in result: {result}"
    assert "2\tline two" in result, f"Expected line 2 content in result: {result}"
    assert "3\tline three" in result, f"Expected line 3 content in result: {result}"


def test_glob_matching(tmp_path: Path):
    """glob returns matching file paths for a given pattern."""
    import clearink.main  # noqa: F401
    from clearink.tool.basetool import glob as glob_handler

    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.txt").write_text("b")
    (tmp_path / "gamma.py").write_text("c")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "delta.txt").write_text("d")

    result = glob_handler(pattern="*.txt", path=str(tmp_path))

    assert "alpha.txt" in result, f"Expected alpha.txt in result: {result}"
    assert "beta.txt" in result, f"Expected beta.txt in result: {result}"
    assert "gamma.py" not in result, f"gamma.py should NOT match *.txt: {result}"
    assert "delta.txt" not in result, "delta.txt is nested, should not match top-level *.txt"

    # Recursive glob
    result_recursive = glob_handler(pattern="**/*.txt", path=str(tmp_path))
    assert "delta.txt" in result_recursive, f"Expected delta.txt in recursive result: {result_recursive}"


# ═══════════════════════════════════════════════════════════════
# 3. DAG task system
# ═══════════════════════════════════════════════════════════════


def _extract_task_id(create_result: str) -> str:
    """Extract numeric task ID from a create_task output line like '[ ] #1: ...'."""
    for line in create_result.splitlines():
        line = line.strip()
        if line.startswith("[") and "#" in line:
            # Matches "[ ] #42: subject" or similar
            after_hash = line.split("#", 1)[1]
            tid = after_hash.split(":", 1)[0].strip()
            return tid
    # Fallback: grab the first number found in the result
    import re
    match = re.search(r"#(\d+)", create_result)
    if match:
        return match.group(1)
    raise AssertionError(f"Could not extract task ID from: {create_result}")


def test_task_system_dag_flow():
    """Full DAG task lifecycle: create A, create B blocked by A, verify B cannot
    start, claim + complete A, verify B can start, claim + complete B."""
    import clearink.main  # noqa: F401
    from clearink.tool.task_system import create_task, claim_task, complete_task, get_task, check_task

    # 1. Create task A (no dependencies)
    result_a = create_task(subject="Task A")
    task_a_id = _extract_task_id(result_a)
    assert task_a_id, f"Could not parse task A ID from: {result_a}"

    # 2. Create task B blocked by A
    result_b = create_task(subject="Task B", blockedBy=[task_a_id])
    task_b_id = _extract_task_id(result_b)
    assert task_b_id, f"Could not parse task B ID from: {result_b}"

    # 3. Verify B cannot start because A is not completed
    check_b = check_task(task_id=task_b_id)
    assert "blocked" in check_b.lower() or "ready" not in check_b.lower(), (
        f"Task B should be blocked initially: {check_b}"
    )

    # 4. Claim B should fail
    claim_b_fail = claim_task(task_id=task_b_id)
    assert "blocked" in claim_b_fail.lower() or "Error" in claim_b_fail, (
        f"Claiming B before A completes should fail: {claim_b_fail}"
    )

    # 5. Claim and complete task A
    claim_a = claim_task(task_id=task_a_id)
    assert "claimed" in claim_a.lower() or "Error" not in claim_a, (
        f"Should claim task A: {claim_a}"
    )

    complete_a = complete_task(task_id=task_a_id)
    assert "completed" in complete_a.lower(), f"Should complete task A: {complete_a}"
    # Completing A should automatically unblock B
    assert "Unblocked" in complete_a, f"Expected Unblocked message: {complete_a}"

    # 6. Verify B can now start
    check_b_after = check_task(task_id=task_b_id)
    assert "ready" in check_b_after.lower(), f"Task B should be ready now: {check_b_after}"

    # 7. Claim and complete task B
    claim_b = claim_task(task_id=task_b_id)
    assert "claimed" in claim_b.lower(), f"Should claim task B: {claim_b}"

    complete_b = complete_task(task_id=task_b_id)
    assert "completed" in complete_b.lower(), f"Should complete task B: {complete_b}"

    # 8. Verify final state via get_task
    state_a = get_task(task_id=task_a_id)
    assert "completed" in state_a, f"Task A should be completed: {state_a}"

    state_b = get_task(task_id=task_b_id)
    assert "completed" in state_b, f"Task B should be completed: {state_b}"


