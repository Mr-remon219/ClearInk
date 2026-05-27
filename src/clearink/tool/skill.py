from pathlib import Path

from clearink.tool.register import register_tool
from ..config import SKILLS_DIR


class Skill:
    def __init__(self):
        self.AVAILABLE_SKILLS: dict[str, dict] = {}
        self._scan_skill()

    def _scan_skill(self) -> None:
        if not SKILLS_DIR.exists():
            return

        for d in SKILLS_DIR.iterdir():
            if not d.is_dir():
                continue

            skill_path = d / "SKILL.md"
            if not skill_path.exists():
                continue

            content = skill_path.read_text(encoding="utf-8")
            frontmatter = self._parse_frontmatter(content)
            if not frontmatter:
                continue

            name = frontmatter.get("name", d.name)
            self.AVAILABLE_SKILLS[name] = {
                "name": name,
                "description": frontmatter.get("description", ""),
                "content": content,
            }

    @staticmethod
    def _parse_frontmatter(content: str) -> dict | None:
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        result = {}
        for line in parts[1].strip().split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
        return result if result else None

    def list_skill(self) -> str:
        lines = []
        for info in self.AVAILABLE_SKILLS.values():
            lines.append(f"- {info['name']}: {info['description']}")
        return "\n".join(lines)


_skill = Skill()


def get_available_skills() -> dict[str, dict]:
    return dict(_skill.AVAILABLE_SKILLS)


@register_tool(name="load_skill",
    description="根据skill名称路由并返回其完整内容",
    input_schema={"type": "object","properties": {"name": {"type": "string","description": "要加载的skill名称",},},"required": ["name"],})
def load_skill(name: str) -> str:
    info = _skill.AVAILABLE_SKILLS.get(name)
    if info is None:
        return f"skill调用失败, 原因: 不存在名为 '{name}' 的skill"
    return info["content"]
