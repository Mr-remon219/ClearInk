from __future__ import annotations

import json
import importlib
import shutil
import subprocess

import pytest


@pytest.fixture
def isolated_worktrees(monkeypatch, tmp_path):
    worktree_mod = importlib.import_module("clearink.tool.team.worktree.worktree")

    root = tmp_path / "worktrees"
    monkeypatch.setattr(worktree_mod, "WORKTREES_DIR", root)
    monkeypatch.setattr(worktree_mod, "MAILBOXES_DIR", root / ".mailboxes")
    monkeypatch.setattr(worktree_mod, "BINDINGS_PATH", root / "bindings.json")
    monkeypatch.setattr(worktree_mod, "EVENTS_LOG", root / ".events.jsonl")
    monkeypatch.setattr(worktree_mod, "_BINDINGS_LOCK_PATH", root / ".bindings.lock")
    return worktree_mod


def _read_events(path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_worktree_create_bind_keep_remove_lifecycle(
    isolated_worktrees,
    monkeypatch,
) -> None:
    git_calls: list[list[str]] = []

    def fake_run_git(args: list[str]) -> tuple[bool, str]:
        git_calls.append(args)
        if args[:2] == ["worktree", "add"]:
            path = isolated_worktrees.Path(args[2])
            path.mkdir(parents=True)
            return (True, "")
        if args[:2] == ["worktree", "remove"]:
            path = isolated_worktrees.Path(args[2])
            shutil.rmtree(path)
            return (True, "")
        return (False, "unexpected git call")

    monkeypatch.setattr(isolated_worktrees, "run_git", fake_run_git)

    created = isolated_worktrees.create_worktree("task_1", task_id="42")
    kept = isolated_worktrees.keep_worktree("task_1")
    removed = isolated_worktrees.remove_worktree("task_1", discard_changes=True)

    assert "Worktree 'task_1' created." in created
    assert kept == "Worktree 'task_1' kept."
    assert removed == "Worktree 'task_1' removed."
    assert git_calls[0] == [
        "worktree",
        "add",
        str(isolated_worktrees.WORKTREES_DIR / "task_1"),
        "-b",
        "task/42",
    ]
    assert git_calls[1][-1] == "--force"
    assert json.loads(
        isolated_worktrees.BINDINGS_PATH.read_text(encoding="utf-8")
    ) == {}

    events = _read_events(isolated_worktrees.EVENTS_LOG)
    assert [event["event"] for event in events] == [
        "create",
        "bind",
        "keep",
        "remove",
        "unbind",
    ]
    assert events[1]["task_id"] == "42"


def test_bind_task_respects_validation_boolean(
    isolated_worktrees,
    monkeypatch,
) -> None:
    (isolated_worktrees.WORKTREES_DIR / "bad").mkdir(parents=True)
    monkeypatch.setattr(
        isolated_worktrees,
        "validate_worktree_name",
        lambda _name: (False, ""),
    )

    result = isolated_worktrees.bind_task_to_worktree("1", "bad")

    assert result.startswith("Error: invalid worktree name")


def test_run_git_smoke_uses_temp_repo_only(monkeypatch, tmp_path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")

    git_ops = importlib.import_module("clearink.tool.team.worktree.git_ops")

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.setattr(git_ops, "_REPO_ROOT", tmp_path)

    ok, output = git_ops.run_git(["status", "--porcelain"])

    assert ok is True
    assert output == ""
