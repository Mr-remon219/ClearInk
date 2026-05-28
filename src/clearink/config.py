from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / "data" / "environment" / ".env"
SKILLS_DIR = Path(__file__).resolve().parents[2] / "data" / "skills"
MEMORY_DIR = Path(__file__).resolve().parents[2] / "data" / "system_prompts" / ".memory"
TASKS_DIR = Path(__file__).resolve().parents[2] / "data" / ".tasks"
WORK_DIR = Path().cwd()