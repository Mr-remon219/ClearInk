from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / "data" / "environment" / ".env"
SKILLS_DIR = Path(__file__).resolve().parents[2] / "data" / "skills"
WORK_DIR = Path().cwd()