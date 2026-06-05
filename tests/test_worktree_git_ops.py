import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from clearink.tool.team.worktree.git_ops import validate_worktree_name, run_git


def test_repo_root_env_configures_git_ops_import(tmp_path):
    configured_root = tmp_path / "repo-root"
    configured_root.mkdir()
    src_path = Path(__file__).resolve().parents[1] / "src"
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(src_path)!r}); "
        "from clearink.tool.team.worktree import git_ops; "
        "print(git_ops._REPO_ROOT)"
    )
    env = os.environ.copy()
    env["CLEARINK_REPO_ROOT"] = str(configured_root)

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert Path(result.stdout.strip()) == configured_root


class TestValidateWorktreeName(unittest.TestCase):
    def test_valid_names(self):
        for name in ["task_1_alice", "my-worktree", "dev.branch", "a", "A1-b_c_d"]:
            with self.subTest(name=name):
                ok, reason = validate_worktree_name(name)
                self.assertTrue(ok, f"Expected valid: {name}, got: {reason}")

    def test_invalid_empty(self):
        ok, reason = validate_worktree_name("")
        self.assertFalse(ok)
        self.assertIn("empty", reason)

    def test_invalid_dot(self):
        ok, _ = validate_worktree_name(".")
        self.assertFalse(ok)

    def test_invalid_dotdot(self):
        ok, _ = validate_worktree_name("..")
        self.assertFalse(ok)

    def test_invalid_slash(self):
        ok, _ = validate_worktree_name("a/b")
        self.assertFalse(ok)

    def test_invalid_space(self):
        ok, _ = validate_worktree_name("a b")
        self.assertFalse(ok)

    def test_invalid_colon(self):
        ok, _ = validate_worktree_name("a:b")
        self.assertFalse(ok)

    def test_invalid_star(self):
        ok, _ = validate_worktree_name("a*b")
        self.assertFalse(ok)

    def test_invalid_too_long(self):
        ok, _ = validate_worktree_name("-" * 65)
        self.assertFalse(ok)

    def test_invalid_path_traversal_slash(self):
        ok, _ = validate_worktree_name("/etc/passwd")
        self.assertFalse(ok)

    def test_invalid_path_traversal_parent(self):
        ok, _ = validate_worktree_name("../escape")
        self.assertFalse(ok)

    def test_invalid_bad_start_char(self):
        ok, _ = validate_worktree_name("-badstart")
        self.assertFalse(ok)


class TestRunGit(unittest.TestCase):
    def test_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")
            ok, output = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
            self.assertTrue(ok)
            self.assertEqual(output, "main")

    def test_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error message")
            ok, output = run_git(["bad-command"])
            self.assertFalse(ok)
            self.assertIn("error", output)

    def test_filenotfound(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            ok, output = run_git(["status"])
            self.assertFalse(ok)
            self.assertIn("not found", output.lower())  # or "git command not found"
