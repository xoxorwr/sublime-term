from __future__ import annotations

import json
import os
from functools import lru_cache

import sublime

from . import palette as term_palette
from . import scheme as term_scheme
from .palette import DEFAULT_BG, DEFAULT_FG, SELECTION, SELECTION_FG, full_palette

SCHEME_RESOURCE = "Packages/sublime_term/Terminal.sublime-color-scheme"
STATE_NAME = "sublime_term_theme.json"
PALETTE = full_palette()
PALETTE_256 = PALETTE[:256]
_INDEX = {color: index for index, color in enumerate(PALETTE)}
CURRENT_FG = DEFAULT_FG
CURRENT_BG = DEFAULT_BG
CURRENT_SELECTION = SELECTION
CURRENT_SELECTION_FG = SELECTION_FG


@lru_cache(maxsize=16384)
def _nearest(rgb):
    best = 0
    best_distance = None
    r, g, b = rgb
    for index, (pr, pg, pb) in enumerate(PALETTE):
        distance = (r - pr) * (r - pr) + (g - pg) * (g - pg) + (b - pb) * (b - pb)
        if best_distance is None or distance < best_distance:
            best = index
            best_distance = distance
            if distance == 0:
                break
    return best


def index(rgb):
    return _INDEX.get(tuple(rgb), _nearest(tuple(rgb)))


def quantize(rgb):
    return PALETTE[index(rgb)]


def scope(fg, bg):
    return "sublime_term.{}.{}".format(index(fg), index(bg))


def underline_scope(color):
    return scope(color, CURRENT_BG)


def apply(view: sublime.View):
    if view.settings().get("color_scheme") != SCHEME_RESOURCE:
        view.settings().set("color_scheme", SCHEME_RESOURCE)


def reload(view: sublime.View):
    if not view.is_valid():
        return
    view.settings().set(
        "color_scheme",
        "Packages/Color Scheme - Default/Monokai.sublime-color-scheme",
    )
    sublime.set_timeout(
        lambda: view.settings().set("color_scheme", SCHEME_RESOURCE)
        if view.is_valid()
        else None,
        0,
    )


def default_fg():
    return CURRENT_FG


def default_bg():
    return CURRENT_BG


def scheme_path():
    return os.path.join(sublime.packages_path(), "sublime_term", "Terminal.sublime-color-scheme")


def state_path():
    return os.path.join(sublime.packages_path(), "User", STATE_NAME)


def _write_state(data):
    path = state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(temp, path)


def _state_data(sha256):
    return {
        "palette": [list(color) for color in PALETTE],
        "foreground": list(CURRENT_FG),
        "background": list(CURRENT_BG),
        "selection": CURRENT_SELECTION,
        "selection_foreground": CURRENT_SELECTION_FG,
        "scheme_sha256": sha256,
    }


def set_palette(palette, foreground, background, selection, selection_fg):
    global PALETTE, PALETTE_256, _INDEX
    global CURRENT_FG, CURRENT_BG, CURRENT_SELECTION, CURRENT_SELECTION_FG
    PALETTE = [tuple(color) for color in palette]
    PALETTE_256 = PALETTE[:256]
    _INDEX = {color: index for index, color in enumerate(PALETTE)}
    CURRENT_FG = tuple(foreground)
    CURRENT_BG = tuple(background)
    CURRENT_SELECTION = selection
    CURRENT_SELECTION_FG = selection_fg
    _nearest.cache_clear()


def sync_to_theme(info):
    palette, foreground, background, selection, selection_fg = term_palette.adaptive_palette(info)
    path = scheme_path()
    term_scheme.write(path, palette, foreground, background, selection, selection_fg)
    set_palette(palette, foreground, background, selection, selection_fg)
    _write_state(_state_data(term_scheme.digest(path)))


def _load_state():
    try:
        if not os.path.exists(state_path()):
            return False
        with open(state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        palette = [tuple(color) for color in data["palette"]]
        if len(palette) != len(PALETTE):
            return False
        foreground = tuple(data["foreground"])
        background = tuple(data["background"])
        selection = data["selection"]
        selection_fg = data["selection_foreground"]
        path = scheme_path()
        if not os.path.exists(path) or term_scheme.digest(path) != data.get("scheme_sha256"):
            term_scheme.write(path, palette, foreground, background, selection, selection_fg)
            data["scheme_sha256"] = term_scheme.digest(path)
            _write_state(data)
        set_palette(palette, foreground, background, selection, selection_fg)
        return True
    except Exception as e:
        print("sublime_term: could not load saved theme:", e)
        return False


_initialized = False


def ensure_initialized():
    global _initialized
    if _initialized:
        return
    _initialized = True
    if _load_state():
        return
    try:
        sync_to_theme(sublime.ui_info())
    except Exception as e:
        print("sublime_term: could not initialize theme:", e)
        _initialized = False
