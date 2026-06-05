import time
from datetime import datetime
from pathlib import Path

from clearink.config import LOGS_DIR
from .hook import hook_context, register_hook

_PAPER_EXTENSIONS = {".pdf", ".txt", ".md"}
_PAPER_KEYWORDS = {
    "paper", "arxiv", "article", "publication", "manuscript",
    "preprint", "chapter",
}

_CITATION_TRIGGERS = {
    "cite", "citation", "citations",
    "reference", "references",
    "bibliography", "bibtex",
    "according to",
    "published in",
    "how to cite",
    "find the paper",
    "what did",
    "et al",
}

_CITATION_REMINDER = (
    "[System: The user appears to be asking about a citation or paper reference. "
    "Do NOT generate author names, journal names, years, or page numbers from memory. "
    "Use scholar search or lookup to retrieve verified metadata. "
    "Present ONLY fields returned by the BibTeX output.]"
)

_JOURNAL_PATH = LOGS_DIR / "reading-journal.md"


def _looks_like_paper(file_path: str) -> bool:
    p = Path(file_path)
    stem_lower = p.stem.lower()
    return p.suffix.lower() in _PAPER_EXTENSIONS or any(
        kw in stem_lower for kw in _PAPER_KEYWORDS
    )


@register_hook("pretooluse", name="track_reading_context", priority=0)
def track_reading_context(context: dict) -> None:
    tool_name = context.get("tool_name", "")
    arguments = context.get("arguments", {})

    file_path: str | None = None
    if tool_name == "read_file":
        file_path = arguments.get("file_path")
    elif tool_name == "glob":
        pattern = arguments.get("pattern", "")
        if any(pattern.lower().endswith(ext) for ext in _PAPER_EXTENSIONS):
            file_path = pattern

    if not file_path or not _looks_like_paper(file_path):
        return

    ctx = context.setdefault("hook_context", hook_context)
    now = time.time()

    ctx["current_paper"] = {
        "path": file_path,
        "name": Path(file_path).stem,
        "opened_at": now,
    }

    existing = [p for p in ctx["papers_accessed"] if p["path"] == file_path]
    if existing:
        existing[0]["access_count"] += 1
        existing[0]["last_seen"] = now
    else:
        ctx["papers_accessed"].append({
            "path": file_path,
            "name": Path(file_path).stem,
            "access_count": 1,
            "first_seen": now,
            "last_seen": now,
        })


@register_hook("userpromptsubmit", name="detect_citation_request", priority=0)
def detect_citation_request(context: dict) -> None:
    messages = context.get("messages", [])
    if not messages:
        return

    last = messages[-1]
    content = ""
    if isinstance(last, dict) and "content" in last:
        content = last["content"] if isinstance(last["content"], str) else ""

    if not content:
        return

    lower = content.lower()
    ctx = context.setdefault("hook_context", hook_context)
    if any(trigger in lower for trigger in _CITATION_TRIGGERS):
        ctx["citation_requested"] = True
    else:
        ctx["citation_requested"] = False


@register_hook("userpromptsubmit", name="suggest_citation_tool", priority=50)
def suggest_citation_tool(context: dict) -> None:
    ctx = context.get("hook_context", {})
    if not ctx.get("citation_requested"):
        return

    messages = context.get("messages", [])
    if not messages:
        return

    recent_scholar = any(
        isinstance(m, dict)
        and m.get("role") in ("assistant", "user")
        and "scholar" in str(m.get("content", "")).lower()
        for m in messages[-6:]
    )
    if recent_scholar:
        return

    messages.append({"role": "user", "content": _CITATION_REMINDER})


def _format_journal_entry(context: dict) -> str:
    ctx = context.get("hook_context", {})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    turn = context.get("turns", 0)
    current_paper = ctx.get("current_paper")
    paper_name = current_paper["name"] if current_paper else "N/A"
    citation_flag = ctx.get("citation_requested", False)

    lines = [
        f"## Turn {turn} -- {now}",
        f"- **Paper:** {paper_name}",
        f"- **Citation requested:** {citation_flag}",
        f"- **Papers accessed so far:** {len(ctx.get('papers_accessed', []))}",
        "",
    ]

    messages = context.get("messages", [])
    if messages:
        last_user = None
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, str):
                    last_user = content[:200]
                break
        if last_user:
            lines.append(f"### Last user query\n> {last_user}\n")

    return "\n".join(lines)


@register_hook("stop", name="log_turn_to_journal", priority=100)
def log_turn_to_journal(context: dict) -> None:
    if not context.get("messages"):
        return

    entry = _format_journal_entry(context)
    _JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    header = "# Reading Session Journal\n\n" if not _JOURNAL_PATH.exists() else ""

    with open(_JOURNAL_PATH, "a" if _JOURNAL_PATH.exists() else "w", encoding="utf-8") as f:
        if header:
            f.write(header)
        f.write(entry)
        f.write("\n\n---\n\n")
