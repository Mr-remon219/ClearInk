from __future__ import annotations
import os
import re
from anthropic import Anthropic
from dotenv import load_dotenv

from ..config import ENV_PATH, MEMORY_DIR
from ..message import extract_text_from_content, sanitize_messages_for_no_thinking
from .memory_store import is_valid_memory_name, list_memory_files, read_memory_index, read_memory_file
from .system_build import set_current_memories

load_dotenv(ENV_PATH, override=True)
_sub_client: Anthropic | None = None
_sub_model = os.getenv("SUBAGENT_MODEL", "deepseek-v4-flash")


def _get_sub_client() -> Anthropic:
    global _sub_client
    if _sub_client is None:
        _sub_client = Anthropic()
    return _sub_client


def _last_user_message(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                return " ".join(parts)
    return ""


def select_relevant_memories(messages: list) -> list[str]:
    index_text = read_memory_index()
    if not index_text:
        return []

    user_msg = _last_user_message(messages)
    if not user_msg:
        return []

    system_prompt = (
        "You are a memory relevance matcher. Given a list of available memories "
        "and a user query, determine which memories (if any) are relevant to the query. "
        "Return ONLY the memory names from the index, one per line. "
        "If none are relevant, return 'none'."
    )

    user_prompt = (
        f"Available memories:\n{index_text}\n\n"
        f"User query:\n{user_msg}\n\n"
        f"Which memories are relevant? Return names only, one per line, or 'none'."
    )

    try:
        response = _get_sub_client().messages.create(
            model=_sub_model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=512,
            thinking={"type": "disabled"},
        )
    except Exception:
        return []

    text = extract_text_from_content(response.content).strip().lower()

    if not text or text == "none":
        return []

    valid_names = {entry["name"] for entry in list_memory_files()}
    names = []
    for line in text.splitlines():
        candidate = _normalize_memory_candidate(line)
        if candidate and candidate in valid_names:
            names.append(candidate)
    return list(dict.fromkeys(names))


def _normalize_memory_candidate(line: str) -> str:
    candidate = line.strip().strip("- ").strip()
    if not candidate or candidate.lower() == "none":
        return ""

    match = re.search(r"\[([a-z0-9][a-z0-9-]{0,127})\]", candidate)
    if match:
        candidate = match.group(1)
    else:
        candidate = candidate.split()[0].strip()
        if candidate.endswith(".md"):
            candidate = candidate[:-3]

    return candidate if is_valid_memory_name(candidate) else ""


def load_memories(messages: list) -> str:
    names = select_relevant_memories(messages)
    if not names:
        set_current_memories("")
        return ""

    contents = []
    for name in names:
        file_content = read_memory_file(name)
        if file_content:
            contents.append(file_content)

    if not contents:
        set_current_memories("")
        return ""

    result = "\n\n=== Relevant Memories ===\n\n" + "\n\n---\n\n".join(contents)
    set_current_memories(result)
    return result


def extract_memories(messages: list) -> list[dict]:
    if not messages:
        return []

    rules_path = MEMORY_DIR / "memory.md"
    try:
        rules = rules_path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        rules = ""

    index_text = read_memory_index()

    system_prompt = (
        f"{rules}\n\n"
        f"=== Current Memory Index ===\n"
        f"{index_text or '(empty)'}\n"
    )

    user_prompt = (
        "Based on the conversation above, extract any information worth saving to memory. "
        "For each item, provide: name (kebab-case slug), description (one-line summary), "
        "type (user/feedback/project/reference/knowledge), and the full content. "
        "Format each item as:\n\n"
        "---\n"
        "name: <name>\n"
        "description: <description>\n"
        "type: <type>\n"
        "content: |\n"
        "  <multi-line content, indented>\n"
        "---\n\n"
        "If nothing is worth saving, respond with 'none'."
    )

    try:
        clean_messages = sanitize_messages_for_no_thinking(messages)
        response = _get_sub_client().messages.create(
            model=_sub_model,
            system=system_prompt,
            messages=clean_messages + [{"role": "user", "content": user_prompt}],
            max_tokens=2048,
            thinking={"type": "disabled"},
        )
    except Exception:
        return []

    text = extract_text_from_content(response.content).strip()

    if not text or text.lower() == "none":
        return []

    return _parse_extracted_items(text)


def _parse_extracted_items(text: str) -> list[dict]:
    items = []
    blocks = text.split("---")
    for block in blocks:
        block = block.strip()
        if not block or block.lower() == "none":
            continue

        item = {}
        in_content = False
        content_lines = []

        for line in block.splitlines():
            stripped = line.strip()
            if in_content:
                content_lines.append(stripped.lstrip("  "))
                continue
            if ":" in stripped and not stripped.startswith(" "):
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                if key == "content" and value in ("|", ">"):
                    in_content = True
                elif key in ("name", "description", "type"):
                    item[key] = value

        if content_lines:
            item["content"] = "\n".join(content_lines).strip()
        if item.get("name") and item.get("content"):
            items.append(item)

    return items
