from __future__ import annotations

import html
import re

_CODE_FENCE_RE = re.compile(r"(```.*?```)", re.DOTALL)
_DISPLAY_MATH_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", re.DOTALL)

_TEXT_COMMANDS = (
    "text",
    "textbf",
    "textit",
    "mathrm",
    "mathbf",
    "operatorname",
)

_SYMBOL_REPLACEMENTS = {
    r"\downarrow": "->",
    r"\rightarrow": "->",
    r"\to": "->",
    r"\Rightarrow": "=>",
    r"\Leftarrow": "<=",
    r"\leftrightarrow": "<->",
    r"\prod": "prod",
    r"\sum": "sum",
    r"\sqrt": "sqrt",
    r"\sigma": "sigma",
    r"\mu": "mu",
    r"\alpha": "alpha",
    r"\beta": "beta",
    r"\gamma": "gamma",
    r"\delta": "delta",
    r"\epsilon": "epsilon",
    r"\lambda": "lambda",
    r"\theta": "theta",
    r"\pi": "pi",
    r"\times": "*",
    r"\cdot": "*",
    r"\leq": "<=",
    r"\geq": ">=",
    r"\neq": "!=",
    r"\approx": "~=",
    r"\quad": " ",
    r"\qquad": " ",
    r"\,": " ",
    r"\;": ";",
    r"\:": " ",
    r"\!": "",
}


def format_response_text(text: str) -> str:
    """Make model output readable in terminals that cannot render LaTeX."""
    if not text:
        return text

    chunks = _CODE_FENCE_RE.split(text)
    formatted = []
    for chunk in chunks:
        if chunk.startswith("```") and chunk.endswith("```"):
            formatted.append(chunk)
        else:
            formatted.append(_format_math(chunk))
    return "".join(formatted).strip()


def _format_math(text: str) -> str:
    text = html.unescape(text)
    text = _DISPLAY_MATH_RE.sub(
        lambda match: f"\n\n{_latex_to_text(match.group(1))}\n\n",
        text,
    )
    text = _INLINE_MATH_RE.sub(
        lambda match: _latex_to_text(match.group(1)),
        text,
    )
    text = re.sub(r"\n[ \t]+\n", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _latex_to_text(source: str) -> str:
    text = source.replace("\r\n", " ").replace("\n", " ")
    text = _replace_latex_wrappers(text)
    text = _replace_fractions(text)
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", text)

    for raw, replacement in _SYMBOL_REPLACEMENTS.items():
        text = text.replace(raw, replacement)

    text = text.replace(r"\left", "").replace(r"\right", "")
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    text = _replace_scripts(text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:)\]])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    text = re.sub(r"(\d+/\d+)(?=[A-Za-z])", r"\1 ", text)
    text = re.sub(r"\s*;\s*(=>|<=|->|<-|<->)\s*;\s*", r" \1 ", text)
    text = re.sub(r"\s*(=>|<=|>=|!=|~=|->|<-|<->)\s*", r" \1 ", text)
    text = re.sub(r"\s*(?<![<>!~])=(?!>)\s*", " = ", text)
    text = re.sub(r"\s*([+*])\s*", r" \1 ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _replace_latex_wrappers(text: str) -> str:
    pattern = re.compile(
        r"\\(" + "|".join(re.escape(command) for command in _TEXT_COMMANDS) + r")\{([^{}]*)\}",
    )
    previous = None
    while text != previous:
        previous = text
        text = pattern.sub(lambda match: match.group(2), text)
    return text


def _replace_fractions(text: str) -> str:
    pattern = re.compile(r"\\(?:tfrac|frac)\{([^{}]+)\}\{([^{}]+)\}")
    previous = None
    while text != previous:
        previous = text
        text = pattern.sub(lambda match: f"{match.group(1)}/{match.group(2)}", text)
    return text


def _replace_scripts(text: str) -> str:
    text = re.sub(
        r"_\{([^{}]+)\}",
        lambda match: _ascii_script("_", match.group(1)),
        text,
    )
    return re.sub(
        r"\^\{([^{}]+)\}",
        lambda match: _ascii_script("^", match.group(1)),
        text,
    )


def _ascii_script(marker: str, value: str) -> str:
    if len(value) == 1:
        return f"{marker}{value}"
    return f"{marker}({value})"
