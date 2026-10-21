from __future__ import annotations

DEFAULT_FG = (216, 222, 233)
DEFAULT_BG = (30, 30, 30)
DEFAULT_FG_INDEX = 256
DEFAULT_BG_INDEX = 257
SELECTION = "#3b4252"
SELECTION_FG = "#eceff4"


def xterm_palette():
    colors = [
        (0x00, 0x00, 0x00), (0x80, 0x00, 0x00), (0x00, 0x80, 0x00), (0x80, 0x80, 0x00),
        (0x00, 0x00, 0x80), (0x80, 0x00, 0x80), (0x00, 0x80, 0x80), (0xc0, 0xc0, 0xc0),
        (0x80, 0x80, 0x80), (0xff, 0x00, 0x00), (0x00, 0xff, 0x00), (0xff, 0xff, 0x00),
        (0x00, 0x00, 0xff), (0xff, 0x00, 0xff), (0x00, 0xff, 0xff), (0xff, 0xff, 0xff),
    ]
    levels = (0x00, 0x5f, 0x87, 0xaf, 0xd7, 0xff)
    for r in levels:
        for g in levels:
            for b in levels:
                colors.append((r, g, b))
    for i in range(24):
        value = 8 + i * 10
        colors.append((value, value, value))
    return colors


def full_palette():
    return xterm_palette() + [DEFAULT_FG, DEFAULT_BG]


def _parse_hex(value, fallback):
    if not isinstance(value, str):
        return fallback
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return fallback
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def _to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _mix(a, b, amount):
    return tuple(int(a[i] * (1.0 - amount) + b[i] * amount) for i in range(3))


def _lighten(color, amount):
    return _mix(color, (255, 255, 255), amount)


def _darken(color, amount):
    return _mix(color, (0, 0, 0), amount)


def _luminance(color):
    r, g, b = color
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def adaptive_palette(info):
    palette_info = (info.get("color_scheme") or {}).get("palette") or {}
    background = _parse_hex(palette_info.get("background"), DEFAULT_BG)
    foreground = _parse_hex(palette_info.get("foreground"), DEFAULT_FG)
    is_dark = _luminance(background) < 0.5

    base = xterm_palette()
    red = _parse_hex(palette_info.get("redish"), base[1])
    green = _parse_hex(palette_info.get("greenish"), base[2])
    yellow = _parse_hex(palette_info.get("yellowish") or palette_info.get("orangish"), base[3])
    blue = _parse_hex(palette_info.get("bluish"), base[4])
    magenta = _parse_hex(palette_info.get("pinkish") or palette_info.get("purplish"), base[5])
    cyan = _parse_hex(palette_info.get("cyanish"), base[6])

    normal = [
        (0, 0, 0),
        red,
        green,
        yellow,
        blue,
        magenta,
        cyan,
        foreground,
    ]
    bright_black = _mix(background, foreground, 0.45)
    bright = [bright_black]
    for color in normal[1:]:
        bright.append(_lighten(color, 0.18) if is_dark else _darken(color, 0.18))
    base[0:8] = normal
    base[8:16] = bright

    selection = _to_hex(_mix(background, foreground, 0.25))
    selection_foreground = _to_hex(foreground)
    palette = base + [foreground, background]
    return palette, foreground, background, selection, selection_foreground
