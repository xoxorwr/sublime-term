#!/usr/bin/env python3
"""Generate the default static color scheme used by sublime_term."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from term.palette import DEFAULT_BG, DEFAULT_FG, SELECTION, SELECTION_FG, full_palette  # noqa: E402
from term.scheme import write  # noqa: E402

OUT = os.path.join(ROOT, "Terminal.sublime-color-scheme")


def main():
    write(
        OUT,
        full_palette(),
        DEFAULT_FG,
        DEFAULT_BG,
        SELECTION,
        SELECTION_FG,
    )
    print("wrote", OUT)


if __name__ == "__main__":
    main()
