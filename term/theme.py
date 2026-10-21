from __future__ import annotations

from functools import lru_cache

import sublime

from .palette import DEFAULT_BG, full_palette

SCHEME_RESOURCE = "Packages/sublime_term/Terminal.sublime-color-scheme"
PALETTE = full_palette()
PALETTE_256 = PALETTE[:256]
_INDEX = {color: index for index, color in enumerate(PALETTE)}


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
    return scope(color, DEFAULT_BG)


def apply(view: sublime.View):
    if view.settings().get("color_scheme") != SCHEME_RESOURCE:
        view.settings().set("color_scheme", SCHEME_RESOURCE)
