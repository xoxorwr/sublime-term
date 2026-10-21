from __future__ import annotations

import hashlib
import json
import os


def hex_color(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def write(path, palette, foreground, background, selection, selection_fg):
    rules = []
    background_hex = hex_color(background)
    bumped_background = hex_color((background[0], background[1], min(255, background[2] + 1)))
    default_bg_index = len(palette) - 1
    for fg_index, fg in enumerate(palette):
        for bg_index, bg in enumerate(palette):
            rules.append(
                {
                    "scope": "sublime_term.{}.{}".format(fg_index, bg_index),
                    "foreground": hex_color(fg),
                    "background": bumped_background if bg_index == default_bg_index else hex_color(bg),
                }
            )
    data = {
        "name": "sublime_term",
        "globals": {
            "background": background_hex,
            "foreground": hex_color(foreground),
            "caret": "#00000000",
            "selection": selection,
            "selection_foreground": selection_fg,
            "inactive_selection": selection,
            "inactive_selection_foreground": selection_fg,
            "selection_corner_style": "square",
            "selection_border_width": "0",
            "line_highlight": "#00000000",
            "gutter": background_hex,
            "gutter_foreground": hex_color(foreground),
        },
        "rules": rules,
    }
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(temp, path)


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
