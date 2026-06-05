"""Browser-friendly output formatting.

Unlike ``user/output_format.py`` (which converts LaTeX to ASCII for
terminal display), this module preserves LaTeX delimiters so that
MathJax or KaTeX can render equations in the browser.

Usage in API endpoints::

    from .web_format import format_browser_response
    response = format_browser_response(raw_llm_output)
"""

from __future__ import annotations

import html as html_mod
import re

# Regexes matching the same delimiters as output_format.py
_CODE_FENCE_RE = re.compile(r"(```.*?```)", re.DOTALL)
_DISPLAY_MATH_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", re.DOTALL)


def format_browser_response(text: str) -> str:
    """Format LLM output for browser rendering with MathJax / KaTeX.

    - Preserves ``$$...$$`` (display math) and ``$...$`` (inline math).
    - HTML-escapes everything *except* math blocks and code fences.
    - Collapses runs of blank lines.

    Returns a string ready to be passed through a Markdown renderer
    + MathJax/KaTeX on the frontend.
    """
    if not text:
        return text

    chunks = _CODE_FENCE_RE.split(text)
    formatted = []

    for chunk in chunks:
        if chunk.startswith("```") and chunk.endswith("```"):
            # Code fence — pass through untouched
            formatted.append(chunk)
        else:
            formatted.append(_format_text_block(chunk))

    result = "".join(formatted).strip()
    # Collapse runs of blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def _format_text_block(text: str) -> str:
    """HTML-escape everything EXCEPT LaTeX math delimiters."""
    # Split on display math — keep math raw, escape the rest
    parts = _DISPLAY_MATH_RE.split(text)
    escaped = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Odd-indexed parts are display math — wrap in $$ and leave raw
            escaped.append(f"$${part}$$")
        else:
            # Even-indexed parts are plain text — do inline-math handling
            escaped.append(_escape_with_inline_math(part))
    return "".join(escaped)


def _escape_with_inline_math(text: str) -> str:
    """HTML-escape text but preserve ``$...$`` inline math."""
    parts = _INLINE_MATH_RE.split(text)
    escaped = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Inline math — wrap and leave raw
            escaped.append(f"${part}$")
        else:
            # Plain text — HTML-escape
            escaped.append(html_mod.escape(part, quote=False))
    return "".join(escaped)
