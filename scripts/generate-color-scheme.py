#!/usr/bin/env python3
"""Generate the default static color scheme in the Sublime user directory."""

import argparse
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from term.palette import DEFAULT_BG, DEFAULT_FG, SELECTION, SELECTION_FG, full_palette  # noqa: E402
from term.scheme import write  # noqa: E402


def default_output():
    if ROOT.parent.name == "Packages":
        user = ROOT.parent / "User"
    else:
        system = platform.system()
        if system == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            user = base / "Sublime Text" / "Packages" / "User"
        elif system == "Darwin":
            user = Path.home() / "Library" / "Application Support" / "Sublime Text" / "Packages" / "User"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            user = base / "sublime-text" / "Packages" / "User"
    return user / "SublimeTerm" / "Terminal.sublime-color-scheme"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(default_output()), help="output scheme path")
    args = parser.parse_args()
    path = Path(args.out).expanduser()
    write(
        str(path),
        full_palette(),
        DEFAULT_FG,
        DEFAULT_BG,
        SELECTION,
        SELECTION_FG,
    )
    print("wrote", path)


if __name__ == "__main__":
    main()
