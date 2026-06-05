import os
from pathlib import Path

WORK_DIR = Path().cwd()
_SOURCE_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _resolve_repo_root() -> Path:
    env_repo_root = os.getenv("CLEARINK_REPO_ROOT")
    if env_repo_root:
        return Path(env_repo_root).expanduser()

    return WORK_DIR


def _resolve_data_dir() -> Path:
    env_data_dir = os.getenv("CLEARINK_DATA_DIR")
    if env_data_dir:
        return Path(env_data_dir).expanduser()

    cwd_data_dir = WORK_DIR / "data"
    if cwd_data_dir.exists():
        return cwd_data_dir

    if _SOURCE_DATA_DIR.exists():
        return _SOURCE_DATA_DIR

    return cwd_data_dir


REPO_ROOT = _resolve_repo_root()
DATA_DIR = _resolve_data_dir()
ENV_PATH = DATA_DIR / "environment" / ".env"
SYSTEM_PROMPTS_DIR = DATA_DIR / "system_prompts"
SKILLS_DIR = DATA_DIR / "skills"
MEMORY_DIR = SYSTEM_PROMPTS_DIR / ".memory"
TASKS_DIR = DATA_DIR / ".tasks"
WORKTREES_DIR = TASKS_DIR / ".worktrees"
TASK_OUTPUTS_DIR = DATA_DIR / "task_outputs"
TRANSCRIPTS_DIR = DATA_DIR / ".transcripts"
LOGS_DIR = DATA_DIR / "logs"
TEAM_DIR = DATA_DIR / "team"
SCHEDULED_TASKS_DIR = DATA_DIR / ".scheduled_tasks"
MCP_CONFIG_PATH = DATA_DIR / "mcp" / "servers.json"
