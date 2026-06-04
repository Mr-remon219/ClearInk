from __future__ import annotations
import re
import frontmatter

from ..config import MEMORY_DIR

_EXCLUDED = {"memory.md", "MEMORY.md"}
_VALID_TYPES = {"user", "feedback", "project", "reference", "knowledge"}
_MEMORY_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")


def is_valid_memory_name(name: str) -> bool:
    return bool(_MEMORY_NAME_RE.fullmatch(name))


def _memory_path(name: str):
    if not is_valid_memory_name(name):
        raise ValueError(
            "Memory name must be a kebab-case slug using lowercase letters, "
            "numbers, and hyphens."
        )
    return MEMORY_DIR / f"{name}.md"


def _parse_frontmatter(content: str) -> dict | None:
    try:
        post = frontmatter.loads(content)
        return dict(post.metadata)
    except Exception:
        return None


def read_memory_index() -> str:
    path = MEMORY_DIR / "MEMORY.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, FileNotFoundError):
        return ""


def list_memory_files() -> list[dict]:
    if not MEMORY_DIR.exists():
        return []
    results = []
    for f in MEMORY_DIR.glob("*.md"):
        if f.name.lower() in _EXCLUDED:
            continue
        try:
            post = frontmatter.load(str(f))
        except Exception:
            continue
        meta = dict(post.metadata)
        entry_name = meta.get("name", f.stem)
        if not is_valid_memory_name(entry_name):
            continue
        results.append({
            "name": entry_name,
            "description": meta.get("description", ""),
            "type": meta.get("metadata", {}).get("type", "") if isinstance(meta.get("metadata"), dict) else meta.get("type", ""),
            "file_path": str(f),
        })
    return results


def read_memory_file(name: str) -> str | None:
    try:
        path = _memory_path(name)
    except ValueError:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return None


def write_memory_file(name: str, description: str, memory_type: str, content: str) -> str:
    path = _memory_path(name)
    if memory_type not in _VALID_TYPES:
        raise ValueError(f"Invalid memory type: {memory_type!r}. Must be one of {sorted(_VALID_TYPES)}")

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    post = frontmatter.Post(
        content,
        name=name,
        description=description,
        metadata={"type": memory_type},
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")

    _rebuild_index()
    return f"Memory '{name}' saved successfully."


def _rebuild_index() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    files = list_memory_files()
    lines = []
    for entry in files:
        entry_name = entry["name"]
        lines.append(f"- [{entry_name}]({entry_name}.md) — {entry['description']}")
    index_path = MEMORY_DIR / "MEMORY.md"
    index_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def consolidate_memories(new_items: list[dict]) -> str:
    updated = []
    added = []

    existing = {entry["name"]: entry for entry in list_memory_files()}

    for item in new_items:
        item_name = item.get("name", "")
        item_desc = item.get("description", "")
        item_type = item.get("type", "knowledge")
        item_content = item.get("content", "")

        if not item_name:
            continue
        if not is_valid_memory_name(item_name):
            continue

        if item_type not in _VALID_TYPES:
            item_type = "knowledge"

        if item_name in existing:
            updated.append(item_name)
        else:
            added.append(item_name)

        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        path = _memory_path(item_name)
        post = frontmatter.Post(
            item_content,
            name=item_name,
            description=item_desc,
            metadata={"type": item_type},
        )
        path.write_text(frontmatter.dumps(post), encoding="utf-8")

    _rebuild_index()

    parts = []
    if updated:
        parts.append(f"updated: [{', '.join(updated)}]")
    if added:
        parts.append(f"added: [{', '.join(added)}]")
    return "; ".join(parts) if parts else "no changes"
