"""
Hashed CLI Banner — # logo + HASHED block-art logo.

Displayed when 'hashed' is called with no subcommand and on 'hashed version'.

The `#` symbol is the Hashed brand mark:
  - # = hash  (the product name)
  - # = shell comment / code marker  (the developer audience)
  - # = hashtag  (the social/community dimension)

No external dependencies — only Rich (already in hashed-sdk core deps).
"""
from __future__ import annotations

from rich.console import Console
from rich.text import Text

# ── # symbol in block art (6 lines, same height as HASHED text) ──────────────
#
#  Classic hash/pound rendered with ██ characters.
#  Width ~18 chars — matches original mascot column width.
#
_HASH_LINES = [
    "   ██    ██    ",
    " ████████████    ",
    "   ██    ██    ",
    " ████████████    ",
    "   ██    ██    ",
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
_HASH_STYLE    = "bold cyan"          # same brand cyan — # is part of the logo
_HASHED_STYLE  = "bold cyan"          # Hashed brand cyan
_VERSION_STYLE = "bold green"
_TAGLINE_STYLE = "dim white"
_GAP           = "  "                 # horizontal spacing between # and HASHED


def show_banner(version: str = "", tagline: bool = True) -> None:
    """
    Print the Hashed CLI banner to stdout.

    Combines the # logo (left) and HASHED block art (right) side by side,
    followed by an optional tagline + version string.

    Args:
        version:  Version string to append (e.g. ``"0.2.1"``).
                  If empty the version indicator is omitted.
        tagline:  Whether to print the tagline row below the logo.

    Example output::

       ██    ██   ██╗  ██╗  █████╗  ███████╗ ...
       ██    ██   ██║  ██║ ██╔══██╗ ██╔════╝ ...
     ██████████   ███████║ ███████║ ███████╗ ...
     ...
                  🔐  AI Agent Governance & Security   v0.2.1
    """
    console = Console()
    console.print()

    for hash_line, hashed_line in zip(_HASH_LINES, _HASHED_LINES):
        row = Text()
        row.append(hash_line, style=_HASH_STYLE)
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
            f"              🔐  AI Agent Governance & Security"
            f"{ver_str}"
            f"[/{_TAGLINE_STYLE}]"
        )

    console.print()
