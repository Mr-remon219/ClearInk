from rich.console import Console
from rich.style import Style
from rich.text import Text

from .i18n import t

console = Console()

# Color theme
LEMON_YELLOW = Style(color="rgb(255,215,0)")
LEMON_CHEEK = Style(color="rgb(255,180,50)")
LEAF_GREEN = Style(color="rgb(50,180,50)")
DIM_LABEL = Style(color="rgb(140,140,140)", italic=True)

# Lemon pixel art — labels via i18n
LEMON_ROWS = [
    ("      ▄▄           ", t("lemon_name")),
    ("    ▄████▄         ", ""),
    ("   ████████        ", t("lemon_subtitle")),
    ("   ██▓▓▓▓██        ", ""),
    ("    ▀████▀         ", "V1.0-alpha-1"),
    ("      ▀▀           ", ""),
]


def render_lemon() -> None:
    """Render the lemon pixel art with text labels to the console."""
    for art, label in LEMON_ROWS:
        text = Text()
        for ch in art:
            if ch == "█":  # full block
                text.append(ch, style=LEMON_YELLOW)
            elif ch == "▓":  # dark shade (cheek highlight)
                text.append(ch, style=LEMON_CHEEK)
            elif ch in ("▄", "▀"):  # half blocks (leaf)
                text.append(ch, style=LEAF_GREEN)
            else:
                text.append(ch)
        if label:
            text.append("  " + label, style=DIM_LABEL)
        console.print(text)
