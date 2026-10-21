#!/usr/bin/env python3
"""Generate the static 256-color + default scheme used by sublime_term."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from term.palette import DEFAULT_BG, DEFAULT_BG_INDEX, DEFAULT_FG, SELECTION, SELECTION_FG, full_palette  # noqa: E402

OUT = os.path.join(ROOT, "Terminal.sublime-color-scheme")


def hex_color(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def main():
    palette = full_palette()
    rules = []
    background = hex_color(DEFAULT_BG)
    bumped_background = hex_color((DEFAULT_BG[0], DEFAULT_BG[1], min(255, DEFAULT_BG[2] + 1)))
    for fg_index, fg in enumerate(palette):
        for bg_index, bg in enumerate(palette):
            rules.append(
                {
                    "scope": "sublime_term.{}.{}".format(fg_index, bg_index),
                    "foreground": hex_color(fg),
                    "background": bumped_background if bg_index == DEFAULT_BG_INDEX else hex_color(bg),
                }
            )
    data = {
        "name": "sublime_term",
        "globals": {
            "background": background,
            "foreground": hex_color(DEFAULT_FG),
            "caret": "#00000000",
            "selection": SELECTION,
            "selection_foreground": SELECTION_FG,
            "inactive_selection": SELECTION,
            "inactive_selection_foreground": SELECTION_FG,
            "selection_corner_style": "square",
            "selection_border_width": "0",
            "line_highlight": "#00000000",
            "gutter": background,
            "gutter_foreground": hex_color(DEFAULT_FG),
        },
        "rules": rules,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print("wrote", OUT, "with", len(rules), "rules")


if __name__ == "__main__":
    main()
