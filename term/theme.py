from __future__ import annotations

import json
import os

import sublime

DEFAULT_THEME = {
    "foreground": "#d8dee9",
    "background": "#1e1e1e",
    "cursor": "#d8dee9",
    "selection": "#3b4252",
    "selection_foreground": "#eceff4",
}


def _norm(hex_color: str) -> str:
    return hex_color.lower().lstrip("#")


def _bump(hex_color: str) -> str:
    h = _norm(hex_color)
    if len(h) != 6:
        return h
    try:
        value = int(h[4:], 16)
    except ValueError:
        return h
    value = min(255, value + 1)
    return "{}{:02x}".format(h[:4], value)


class ColorSchemeManager:
    def __init__(self):
        self.theme = dict(DEFAULT_THEME)
        self.pairs = set()
        self.underlines = set()
        self.version = 0
        self.written_version = -1
        self.path = self._make_path()
        self.resource = "Packages/sublime_term/sublime_term.hidden-color-scheme"
        self._write()

    def _make_path(self) -> str:
        folder = os.path.join(sublime.packages_path(), "sublime_term")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "sublime_term.hidden-color-scheme")

    def configure(self, theme: dict):
        changed = False
        for key, value in theme.items():
            if key in self.theme and value and self.theme[key] != value:
                self.theme[key] = value
                changed = True
        if changed:
            self.version += 1
            self._write()

    def scope(self, fg, bg) -> str:
        fg = _norm(fg)
        bg = _norm(bg)
        key = (fg, bg)
        if key not in self.pairs:
            self.pairs.add(key)
            self.version += 1
        return "sublime_term.{}.{}".format(fg, bg)

    def underline_scope(self, color) -> str:
        color = _norm(color)
        if color not in self.underlines:
            self.underlines.add(color)
            self.version += 1
        return "sublime_term.ul.{}".format(color)

    def refresh_if_needed(self) -> bool:
        if self.version != self.written_version:
            self._write()
            return True
        return False

    def _write(self):
        bg = _norm(self.theme["background"])
        fg = _norm(self.theme["foreground"])
        rules = []
        for fg_color, bg_color in sorted(self.pairs):
            rule_bg = _bump(bg_color) if bg_color == bg else bg_color
            rules.append(
                {
                    "scope": "sublime_term.{}.{}".format(fg_color, bg_color),
                    "foreground": "#" + fg_color,
                    "background": "#" + rule_bg,
                }
            )
        for color in sorted(self.underlines):
            rules.append({"scope": "sublime_term.ul.{}".format(color), "foreground": "#" + color})
        rules.append({"scope": "sublime_term.plain", "foreground": "#" + fg})
        data = {
            "name": "sublime_term",
            "globals": {
                "background": "#" + bg,
                "foreground": "#" + fg,
                "caret": "#00000000",
                "selection": self.theme["selection"],
                "selection_foreground": self.theme["selection_foreground"],
                "inactive_selection": self.theme["selection"],
                "inactive_selection_foreground": self.theme["selection_foreground"],
                "selection_corner_style": "square",
                "selection_border_width": "0",
                "line_highlight": "#00000000",
                "gutter": "#" + bg,
                "gutter_foreground": "#" + fg,
            },
            "rules": rules,
        }
        temp = self.path + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(temp, self.path)
        self.written_version = self.version

    def apply(self, view: sublime.View):
        if view.settings().get("color_scheme") != self.resource:
            view.settings().set("color_scheme", self.resource)


_manager = None


def manager() -> ColorSchemeManager:
    global _manager
    if _manager is None:
        _manager = ColorSchemeManager()
    return _manager
