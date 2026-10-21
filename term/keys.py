from __future__ import annotations

from . import ghostty

KEY_NAMES = {
    "unidentified": 0,
    "`": 1,
    "backquote": 1,
    "\\": 2,
    "backslash": 2,
    "[": 3,
    "bracket_left": 3,
    "]": 4,
    "bracket_right": 4,
    ",": 5,
    "comma": 5,
    "0": 6,
    "1": 7,
    "2": 8,
    "3": 9,
    "4": 10,
    "5": 11,
    "6": 12,
    "7": 13,
    "8": 14,
    "9": 15,
    "=": 16,
    "equal": 16,
    "a": 20,
    "b": 21,
    "c": 22,
    "d": 23,
    "e": 24,
    "f": 25,
    "g": 26,
    "h": 27,
    "i": 28,
    "j": 29,
    "k": 30,
    "l": 31,
    "m": 32,
    "n": 33,
    "o": 34,
    "p": 35,
    "q": 36,
    "r": 37,
    "s": 38,
    "t": 39,
    "u": 40,
    "v": 41,
    "w": 42,
    "x": 43,
    "y": 44,
    "z": 45,
    "-": 46,
    "minus": 46,
    ".": 47,
    "period": 47,
    "'": 48,
    "quote": 48,
    ";": 49,
    "semicolon": 49,
    "/": 50,
    "slash": 50,
    "alt": 51,
    "alt_left": 51,
    "alt_gr": 52,
    "alt_right": 52,
    "backspace": 53,
    "caps_lock": 54,
    "context_menu": 55,
    "control": 56,
    "control_left": 56,
    "control_right": 57,
    "enter": 58,
    "return": 58,
    "meta": 59,
    "meta_left": 59,
    "meta_right": 60,
    "shift": 61,
    "shift_left": 61,
    "shift_right": 62,
    "space": 63,
    "tab": 64,
    "convert": 65,
    "kana_mode": 66,
    "non_convert": 67,
    "delete": 68,
    "end": 69,
    "help": 70,
    "home": 71,
    "insert": 72,
    "page_down": 73,
    "page_up": 74,
    "down": 75,
    "left": 76,
    "right": 77,
    "up": 78,
    "num_lock": 79,
    "keypad_0": 80,
    "keypad_1": 81,
    "keypad_2": 82,
    "keypad_3": 83,
    "keypad_4": 84,
    "keypad_5": 85,
    "keypad_6": 86,
    "keypad_7": 87,
    "keypad_8": 88,
    "keypad_9": 89,
    "keypad_add": 90,
    "keypad_backspace": 91,
    "keypad_clear": 92,
    "keypad_clear_entry": 93,
    "keypad_comma": 94,
    "keypad_decimal": 95,
    "keypad_divide": 96,
    "keypad_enter": 97,
    "keypad_equal": 98,
    "keypad_subtract": 107,
    "keypad_multiply": 104,
    "keypad_up": 109,
    "keypad_down": 110,
    "keypad_right": 111,
    "keypad_left": 112,
    "escape": 120,
    "esc": 120,
    "f1": 121,
    "f2": 122,
    "f3": 123,
    "f4": 124,
    "f5": 125,
    "f6": 126,
    "f7": 127,
    "f8": 128,
    "f9": 129,
    "f10": 130,
    "f11": 131,
    "f12": 132,
    "f13": 133,
    "f14": 134,
    "f15": 135,
    "f16": 136,
    "f17": 137,
    "f18": 138,
    "f19": 139,
    "f20": 140,
    "print_screen": 148,
    "scroll_lock": 149,
    "pause": 150,
    "audio_volume_down": 169,
    "audio_volume_mute": 170,
    "audio_volume_up": 171,
}

SHIFTED = {
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
    ")": "0",
    "_": "minus",
    "+": "equal",
    "{": "bracket_left",
    "}": "bracket_right",
    "|": "backslash",
    ":": "semicolon",
    '"': "quote",
    "<": "comma",
    ">": "period",
    "?": "slash",
    "~": "backquote",
}


def mods_from_names(names) -> int:
    mods = 0
    if not names:
        return mods
    for name in names:
        name = name.lower()
        if name in ("shift",):
            mods |= ghostty.MOD_SHIFT
        elif name in ("ctrl", "control"):
            mods |= ghostty.MOD_CTRL
        elif name in ("alt", "option"):
            mods |= ghostty.MOD_ALT
        elif name in ("super", "cmd", "command", "meta"):
            mods |= ghostty.MOD_SUPER
    return mods


def key_code(name: str, text: str = "") -> int:
    if not name:
        return 0
    key = name.lower()
    if key in KEY_NAMES:
        return KEY_NAMES[key]
    if len(key) == 1:
        if key in SHIFTED:
            return KEY_NAMES.get(SHIFTED[key], 0)
        return KEY_NAMES.get(key, 0)
    return 0


def encode(terminal, name: str, mods: int = 0, text: str = "", action: int = ghostty.KEY_ACTION_PRESS):
    code = key_code(name, text)
    if not code:
        if text:
            return text.encode("utf-8")
        return b""
    return terminal.key(code, mods, text, action)
