from __future__ import annotations
from pathlib import Path

_DECISION_KEYWORDS = {
    "decide", "decision", "choose", "chose", "chosen",
    "conclusion", "therefore", "selected", "opted", "agreed",
}

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "it", "its", "this", "that", "these", "those", "i", "you",
    "he", "she", "we", "they", "me", "him", "her", "us", "them",
    "and", "but", "or", "not", "no", "if", "so", "as", "than",
    "then", "also", "just", "about", "into", "over", "after",
    "before", "between", "through", "during", "what", "which",
    "who", "whom", "how", "when", "where", "why", "all", "each",
    "every", "both", "few", "more", "most", "other", "some",
    "such", "only", "own", "same", "very", "my", "your", "his",
}


def build_summary(
    messages: list,
    previous_summary: str | None,
    hook_context: dict,
    transcripts_path: Path,
) -> str:
    lines = [
        f"[Context compacted — full transcript saved to data/.transcripts/{transcripts_path.name}]",
        "",
    ]

    if previous_summary:
        lines.append("=== Previous Summary ===")
        lines.append(previous_summary)
        lines.append("")

    lines.append("=== New Developments ===")

    user_texts = _extract_recent_user_texts(messages, limit=3)
    topics = _extract_key_topics(user_texts)
    if topics:
        lines.append(f"Topics: {', '.join(topics)}")

    decisions = _extract_decisions(user_texts)
    if decisions:
        lines.append(f"Decisions: {'; '.join(decisions)}")

    if not topics and not decisions:
        lines.append("(no significant topics or decisions detected)")

    lines.append("")

    papers = hook_context.get("papers_accessed", [])
    if papers:
        lines.append("=== Recently Accessed ===")
        for p in papers[-10:]:
            name = p.get("name", "unknown")
            path = p.get("path", "")
            count = p.get("access_count", 1)
            lines.append(f"- {name} ({path}, accessed {count} times)")

    return "\n".join(lines)


def _extract_recent_user_texts(messages: list, limit: int) -> list[str]:
    texts = []
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            texts.append(content)
        if len(texts) >= limit:
            break
    return list(reversed(texts))


def _extract_key_topics(texts: list[str]) -> list[str]:
    freq: dict[str, int] = {}
    for text in texts:
        words = text.lower().split()
        for w in words:
            clean = w.strip(".,;:!?()[]{}'\"/").lower()
            if len(clean) >= 3 and clean not in _STOP_WORDS:
                freq[clean] = freq.get(clean, 0) + 1

    scored = [(w, c) for w, c in freq.items() if c >= 2]
    scored.sort(key=lambda x: -x[1])
    return [w for w, _ in scored[:5]]


def _extract_decisions(texts: list[str]) -> list[str]:
    results = []
    for text in texts:
        sentences = text.replace("!", ".").replace("?", ".").split(".")
        for sent in sentences:
            lower = sent.strip().lower()
            if not lower:
                continue
            if any(kw in lower for kw in _DECISION_KEYWORDS):
                clean = sent.strip()[:200]
                if clean not in results:
                    results.append(clean)
    return results[:3]
