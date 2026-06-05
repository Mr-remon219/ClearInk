from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run_config_probe(code: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    src_path = Path(__file__).resolve().parents[1] / "src"
    full_code = (
        "import sys; "
        f"sys.path.insert(0, {str(src_path)!r}); "
        f"{code}"
    )
    return subprocess.run(
        [sys.executable, "-c", full_code],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def test_clearink_data_dir_env_overrides_cwd(tmp_path, monkeypatch) -> None:
    configured = tmp_path / "configured-data"
    cwd = tmp_path / "working-dir"
    cwd.mkdir()
    (cwd / "data").mkdir()
    monkeypatch.setenv("CLEARINK_DATA_DIR", str(configured))

    result = _run_config_probe(
        "from clearink.config import DATA_DIR; print(DATA_DIR)",
        cwd,
    )

    assert Path(result.stdout.strip()) == configured


def test_clearink_repo_root_env_overrides_cwd(tmp_path, monkeypatch) -> None:
    configured = tmp_path / "configured-repo"
    cwd = tmp_path / "working-dir"
    configured.mkdir()
    cwd.mkdir()
    monkeypatch.setenv("CLEARINK_REPO_ROOT", str(configured))

    result = _run_config_probe(
        "from clearink.config import REPO_ROOT; print(REPO_ROOT)",
        cwd,
    )

    assert Path(result.stdout.strip()) == configured


def test_data_dir_prefers_cwd_data_when_env_missing(tmp_path, monkeypatch) -> None:
    cwd = tmp_path / "working-dir"
    cwd_data = cwd / "data"
    cwd_data.mkdir(parents=True)
    monkeypatch.delenv("CLEARINK_DATA_DIR", raising=False)

    env = os.environ.copy()
    env.pop("CLEARINK_DATA_DIR", None)
    src_path = Path(__file__).resolve().parents[1] / "src"
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(src_path)!r}); "
        "from clearink.config import DATA_DIR; print(DATA_DIR)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert Path(result.stdout.strip()) == cwd_data
