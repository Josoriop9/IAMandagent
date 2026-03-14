"""
Hashed CLI Banner — Punch mascot + HASHED block-art logo.

Displayed when 'hashed' is called with no subcommand and on 'hashed version'.
Punch (日本猿) is the Hashed mascot: a cute Japanese snow monkey plush face
that embodies the brand's combination of security (watchful eyes) and
developer-friendliness (ω smile).

No external dependencies — only Rich (already in hashed-sdk core deps).
"""
from __future__ import annotations

from rich.console import Console
from rich.text import Text

# ── Punch plush face (6 lines, right-padded for column alignment) ─────────────
#
#  Design notes:
#   - Round face with ear bumps (╭─╯ ... ╰─╮)
#   - Expressive eyes (◉) with inner brow (╭──╮)
#   - Nose bridge (╰──╯)
#   - Kawaii ω mouth
#   - Warm salmon color (#FF8C6B) — the snow monkey's characteristic pink face
#
_PUNCH_LINES = [
    r"   ╭──────────╮   ",
    r" ╭─╯  ╭────╮  ╰─╮ ",
    r" │   ◉      ◉   │ ",
    r" │    ╰────╯    │ ",
    r" │      ω       │ ",
    r" ╰──────────────╯ ",
]

# ── HASHED in Unicode box-drawing block art (6 lines) ────────────────────────
#
#  Letters: H · A · S · H · E · D
#  Font: custom box-drawing chars (╗ ╔ ║ ═ ╝ ╚)
#  No external figlet/pyfiglet dependency required.
#
_HASHED_LINES = [
    "██╗  ██╗  █████╗  ███████╗██╗  ██╗███████╗██████╗ ",
    "██║  ██║ ██╔══██╗ ██╔════╝██║  ██║██╔════╝██╔══██╗",
    "███████║ ███████║ ███████╗███████║█████╗  ██║  ██║",
    "██╔══██║ ██╔══██║ ╚════██║██╔══██║██╔══╝  ██║  ██║",
    "██║  ██║ ██║  ██║ ███████║██║  ██║███████╗██████╔╝ ",
    "╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═════╝  ",
]

# Palette
_PUNCH_STYLE   = "#FF8C6B"           # warm salmon — snow monkey face
_HASHED_STYLE  = "bold cyan"         # Hashed brand cyan
_VERSION_STYLE = "bold green"
_TAGLINE_STYLE = "dim white"
_GAP           = "   "               # horizontal spacing between face and logo


def show_banner(version: str = "", tagline: bool = True) -> None:
    """
    Print the Hashed CLI banner to stdout.

    Combines the Punch face (left) and HASHED block art (right) into a single
    inline banner, followed by an optional tagline + version string.

    Args:
        version:  Version string to append (e.g. ``"0.2.1"``).
                  If empty the version indicator is omitted.
        tagline:  Whether to print the tagline row below the logo.

    Example output::

       ╭──────────╮    ██╗  ██╗  █████╗  ███████╗ ...
     ╭─╯  ╭────╮  ╰─╮  ██║  ██║ ██╔══██╗ ██╔════╝ ...
     │   ◉      ◉   │  ███████║ ███████║ ███████╗ ...
     ...
                     🔐  AI Agent Governance & Security   v0.2.1
    """
    console = Console()
    console.print()

    for punch_line, hashed_line in zip(_PUNCH_LINES, _HASHED_LINES):
        row = Text()
        row.append(punch_line, style=_PUNCH_STYLE)
        row.append(_GAP)
        row.append(hashed_line, style=_HASHED_STYLE)
        console.print(row)

    if tagline:
        ver_str = (
            f"  [{_VERSION_STYLE}]v{version}[/{_VERSION_STYLE}]"
            if version
            else ""
        )
        console.print(
            f"\n[{_TAGLINE_STYLE}]"
            f"           🔐  AI Agent Governance & Security"
            f"{ver_str}"
            f"[/{_TAGLINE_STYLE}]"
        )

    console.print()
