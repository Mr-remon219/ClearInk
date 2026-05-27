from pathlib import Path

ENV_PATH = Path("__file__").resolve().parents[2] / "environment" / ".env"
SKILLS_DIR = Path("__file__").resolve().parents[2] / "skills"
WORK_DIR = Path().cwd()