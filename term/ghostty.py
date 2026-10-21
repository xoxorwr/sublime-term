from __future__ import annotations

import ctypes as C
import glob
import os
from ctypes import (
    POINTER,
    Structure,
    Union,
    byref,
    c_bool,
    c_char_p,
    c_float,
    c_int,
    c_size_t,
    c_uint8,
    c_uint16,
    c_uint32,
    c_uint64,
    c_void_p,
)


class GhosttyError(RuntimeError):
    pass


class GhosttyNotAvailable(GhosttyError):
    pass


RESULT_SUCCESS = 0
RESULT_OUT_OF_SPACE = -3
RESULT_INVALID_VALUE = -2


class RGB(Structure):
    _fields_ = [("r", c_uint8), ("g", c_uint8), ("b", c_uint8)]

    def hex(self) -> str:
        return "#{:02x}{:02x}{:02x}".format(self.r, self.g, self.b)

    def tuple(self):
        return (self.r, self.g, self.b)


class StyleColorValue(Union):
    _fields_ = [("palette", c_uint8), ("rgb", RGB), ("_padding", c_uint64)]


class StyleColor(Structure):
    _fields_ = [("tag", c_int), ("value", StyleColorValue)]


class Style(Structure):
    _fields_ = [
        ("size", c_size_t),
        ("fg_color", StyleColor),
        ("bg_color", StyleColor),
        ("underline_color", StyleColor),
        ("bold", c_bool),
        ("italic", c_bool),
        ("faint", c_bool),
        ("blink", c_bool),
        ("inverse", c_bool),
        ("invisible", c_bool),
        ("strikethrough", c_bool),
        ("overline", c_bool),
        ("underline", c_int),
    ]


class GhosttyString(Structure):
    _fields_ = [("ptr", POINTER(c_uint8)), ("len", c_size_t)]

    def text(self) -> str:
        if not self.ptr or not self.len:
            return ""
        return bytes(self.ptr[: self.len]).decode("utf-8", "replace")


class GhosttyBuffer(Structure):
    _fields_ = [("ptr", POINTER(c_uint8)), ("cap", c_size_t), ("len", c_size_t)]


class Cursor(Structure):
    _fields_ = [
        ("size", c_size_t),
        ("viewport_has_value", c_bool),
        ("viewport_x", c_uint16),
        ("viewport_y", c_uint16),
        ("wide_tail", c_bool),
        ("visible", c_bool),
        ("blinking", c_bool),
        ("password_input", c_bool),
        ("visual_style", c_int),
    ]


class Colors(Structure):
    _fields_ = [
        ("size", c_size_t),
        ("background", RGB),
        ("foreground", RGB),
        ("cursor", RGB),
        ("cursor_has_value", c_bool),
        ("palette", RGB * 256),
    ]


class Scrollbar(Structure):
    _fields_ = [("total", c_uint64), ("offset", c_uint64), ("len", c_uint64)]


class ModeConfig(Structure):
    _fields_ = [("mode", c_uint16), ("value", c_bool)]


class ScrollViewportValue(Union):
    _fields_ = [("delta", c_uint64), ("row", c_uint64), ("delta_prompt", c_uint64), ("_padding", c_uint64 * 2)]


class ScrollViewport(Structure):
    _fields_ = [("tag", c_int), ("value", ScrollViewportValue)]


class MousePosition(Structure):
    _fields_ = [("x", c_float), ("y", c_float)]


class MouseEncoderSize(Structure):
    _fields_ = [
        ("size", c_size_t),
        ("screen_width", c_uint32),
        ("screen_height", c_uint32),
        ("cell_width", c_uint32),
        ("cell_height", c_uint32),
        ("padding_top", c_uint32),
        ("padding_bottom", c_uint32),
        ("padding_right", c_uint32),
        ("padding_left", c_uint32),
    ]


class ClipboardContent(Structure):
    _fields_ = [("mime", GhosttyString), ("data", GhosttyString)]


ClipboardWriteReplyFn = C.CFUNCTYPE(None, c_void_p, c_void_p)


class ClipboardWrite(Structure):
    _fields_ = [
        ("size", c_size_t),
        ("location", c_int),
        ("contents", POINTER(ClipboardContent)),
        ("contents_len", c_size_t),
        ("name", GhosttyString),
        ("granted", c_bool),
        ("can_remember", c_bool),
        ("ctx", c_void_p),
        ("reply", ClipboardWriteReplyFn),
    ]


class ClipboardWriteReply(Structure):
    _fields_ = [("size", c_size_t), ("result", c_int), ("remember", c_bool)]


class CellData:
    __slots__ = (
        "text",
        "fg",
        "bg",
        "bold",
        "italic",
        "faint",
        "blink",
        "inverse",
        "invisible",
        "strikethrough",
        "overline",
        "underline",
        "underline_color",
        "tail",
    )

    def __init__(self):
        self.text = " "
        self.fg = None
        self.bg = None
        self.bold = False
        self.italic = False
        self.faint = False
        self.blink = False
        self.inverse = False
        self.invisible = False
        self.strikethrough = False
        self.overline = False
        self.underline = 0
        self.underline_color = None
        self.tail = False


class Screen:
    __slots__ = ("cols", "rows", "lines", "cursor", "colors", "scrollbar", "mouse", "title", "pwd", "active_screen")

    def __init__(self):
        self.cols = 0
        self.rows = 0
        self.lines = []
        self.cursor = None
        self.colors = None
        self.scrollbar = None
        self.mouse = False
        self.title = ""
        self.pwd = ""
        self.active_screen = 0


WRITE_PTY_FN = C.CFUNCTYPE(None, c_void_p, c_void_p, POINTER(c_uint8), c_size_t)
BELL_FN = C.CFUNCTYPE(None, c_void_p, c_void_p)
TITLE_FN = C.CFUNCTYPE(None, c_void_p, c_void_p)
PWD_FN = C.CFUNCTYPE(None, c_void_p, c_void_p)
CLIPBOARD_WRITE_FN = C.CFUNCTYPE(None, c_void_p, c_void_p, POINTER(ClipboardWrite))


def _candidate_paths():
    env = os.environ.get("SUBLIME_TERM_LIBGHOSTTY")
    if env:
        yield env
    try:
        import sublime

        settings = sublime.load_settings("sublime_term.sublime-settings")
        configured = settings.get("libghostty_path")
        if configured:
            if not os.path.isabs(configured):
                configured = os.path.join(sublime.packages_path(), configured)
            yield configured
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lib_dir = os.path.join(here, "lib")
        for pattern in (
            "libghostty-vt.so",
            "libghostty-vt.so.*",
            "libghostty-vt.dylib",
            "libghostty-vt.*.dylib",
            "ghostty-vt.dll",
        ):
            for path in sorted(glob.glob(os.path.join(lib_dir, pattern))):
                yield path
    except Exception:
        pass
    for path in (
        "/opt/ghostty/lib/libghostty-vt.so.0",
        "/opt/ghostty/lib/libghostty-vt.so",
        "/opt/ghostty/lib/libghostty-vt.dylib",
        "/opt/homebrew/lib/libghostty-vt.dylib",
        "/usr/local/lib/libghostty-vt.so",
        "/usr/local/lib/libghostty-vt.dylib",
        "/usr/lib/libghostty-vt.so",
    ):
        yield path


_lib = None
_lib_path = None


def lib():
    global _lib, _lib_path
    if _lib is not None:
        return _lib
    errors = []
    for path in _candidate_paths():
        if not path or not os.path.exists(path):
            continue
        try:
            candidate = C.CDLL(path)
            if not hasattr(candidate, "ghostty_terminal_new"):
                errors.append("{}: missing modern terminal API".format(path))
                continue
            _bind(candidate)
            _lib = candidate
            _lib_path = path
            return candidate
        except OSError as e:
            errors.append("{}: {}".format(path, e))
    detail = "\n".join(errors) if errors else "no libghostty-vt candidate found"
    raise GhosttyNotAvailable(
        "Could not load libghostty-vt.\n"
        "Build it with scripts/build_libghostty.py or set libghostty_path.\n"
        + detail
    )


def lib_path():
    lib()
    return _lib_path


def _bind(l):
    def f(name, args, restype):
        fn = getattr(l, name)
        fn.argtypes = args
        fn.restype = restype
        return fn

    l.ghostty_type_json.argtypes = []
    l.ghostty_type_json.restype = c_char_p

    l.ghostty_terminal_new = f("ghostty_terminal_new", [c_void_p, POINTER(c_void_p), c_uint16, c_uint16], c_int)
    l.ghostty_terminal_free = f("ghostty_terminal_free", [c_void_p], None)
    l.ghostty_terminal_reset = f("ghostty_terminal_reset", [c_void_p], None)
    l.ghostty_terminal_resize = f(
        "ghostty_terminal_resize", [c_void_p, c_uint16, c_uint16, c_uint32, c_uint32], c_int
    )
    l.ghostty_terminal_set = f("ghostty_terminal_set", [c_void_p, c_int, c_void_p], c_int)
    l.ghostty_terminal_vt_write = f("ghostty_terminal_vt_write", [c_void_p, c_char_p, c_size_t], None)
    l.ghostty_terminal_get = f("ghostty_terminal_get", [c_void_p, c_int, c_void_p], c_int)
    l.ghostty_terminal_scroll_viewport = f("ghostty_terminal_scroll_viewport", [c_void_p, ScrollViewport], None)

    l.ghostty_render_state_new = f("ghostty_render_state_new", [c_void_p, POINTER(c_void_p)], c_int)
    l.ghostty_render_state_free = f("ghostty_render_state_free", [c_void_p], None)
    l.ghostty_render_state_update = f("ghostty_render_state_update", [c_void_p, c_void_p], c_int)
    l.ghostty_render_state_clean = f("ghostty_render_state_clean", [c_void_p], c_int)
    l.ghostty_render_state_get = f("ghostty_render_state_get", [c_void_p, c_int, c_void_p], c_int)
    l.ghostty_render_state_row_iterator_new = f(
        "ghostty_render_state_row_iterator_new", [c_void_p, POINTER(c_void_p)], c_int
    )
    l.ghostty_render_state_row_iterator_free = f("ghostty_render_state_row_iterator_free", [c_void_p], None)
    l.ghostty_render_state_row_iterator_next = f(
        "ghostty_render_state_row_iterator_next", [c_void_p], c_bool
    )
    l.ghostty_render_state_row_get = f("ghostty_render_state_row_get", [c_void_p, c_int, c_void_p], c_int)
    l.ghostty_render_state_row_cells_new = f(
        "ghostty_render_state_row_cells_new", [c_void_p, POINTER(c_void_p)], c_int
    )
    l.ghostty_render_state_row_cells_free = f("ghostty_render_state_row_cells_free", [c_void_p], None)
    l.ghostty_render_state_row_cells_next = f("ghostty_render_state_row_cells_next", [c_void_p], c_bool)
    l.ghostty_render_state_row_cells_get = f(
        "ghostty_render_state_row_cells_get", [c_void_p, c_int, c_void_p], c_int
    )

    l.ghostty_cell_get = f("ghostty_cell_get", [c_uint64, c_int, c_void_p], c_int)

    l.ghostty_key_encoder_new = f("ghostty_key_encoder_new", [c_void_p, POINTER(c_void_p)], c_int)
    l.ghostty_key_encoder_free = f("ghostty_key_encoder_free", [c_void_p], None)
    l.ghostty_key_encoder_setopt = f("ghostty_key_encoder_setopt", [c_void_p, c_int, c_void_p], None)
    l.ghostty_key_encoder_setopt_from_terminal = f(
        "ghostty_key_encoder_setopt_from_terminal", [c_void_p, c_void_p], None
    )
    l.ghostty_key_encoder_encode = f(
        "ghostty_key_encoder_encode", [c_void_p, c_void_p, c_char_p, c_size_t, POINTER(c_size_t)], c_int
    )
    l.ghostty_key_event_new = f("ghostty_key_event_new", [c_void_p, POINTER(c_void_p)], c_int)
    l.ghostty_key_event_free = f("ghostty_key_event_free", [c_void_p], None)
    l.ghostty_key_event_set_action = f("ghostty_key_event_set_action", [c_void_p, c_int], None)
    l.ghostty_key_event_set_key = f("ghostty_key_event_set_key", [c_void_p, c_int], None)
    l.ghostty_key_event_set_mods = f("ghostty_key_event_set_mods", [c_void_p, c_uint16], None)
    l.ghostty_key_event_set_consumed_mods = f(
        "ghostty_key_event_set_consumed_mods", [c_void_p, c_uint16], None
    )
    l.ghostty_key_event_set_utf8 = f("ghostty_key_event_set_utf8", [c_void_p, c_char_p, c_size_t], None)
    l.ghostty_key_event_set_unshifted_codepoint = f(
        "ghostty_key_event_set_unshifted_codepoint", [c_void_p, c_uint32], None
    )

    l.ghostty_mouse_encoder_new = f("ghostty_mouse_encoder_new", [c_void_p, POINTER(c_void_p)], c_int)
    l.ghostty_mouse_encoder_free = f("ghostty_mouse_encoder_free", [c_void_p], None)
    l.ghostty_mouse_encoder_setopt = f("ghostty_mouse_encoder_setopt", [c_void_p, c_int, c_void_p], None)
    l.ghostty_mouse_encoder_setopt_from_terminal = f(
        "ghostty_mouse_encoder_setopt_from_terminal", [c_void_p, c_void_p], None
    )
    l.ghostty_mouse_encoder_encode = f(
        "ghostty_mouse_encoder_encode", [c_void_p, c_void_p, c_char_p, c_size_t, POINTER(c_size_t)], c_int
    )
    l.ghostty_mouse_event_new = f("ghostty_mouse_event_new", [c_void_p, POINTER(c_void_p)], c_int)
    l.ghostty_mouse_event_free = f("ghostty_mouse_event_free", [c_void_p], None)
    l.ghostty_mouse_event_set_action = f("ghostty_mouse_event_set_action", [c_void_p, c_int], None)
    l.ghostty_mouse_event_set_button = f("ghostty_mouse_event_set_button", [c_void_p, c_int], None)
    l.ghostty_mouse_event_clear_button = f("ghostty_mouse_event_clear_button", [c_void_p], None)
    l.ghostty_mouse_event_set_mods = f("ghostty_mouse_event_set_mods", [c_void_p, c_uint16], None)
    l.ghostty_mouse_event_set_position = f("ghostty_mouse_event_set_position", [c_void_p, MousePosition], None)

    l.ghostty_paste_encode = f(
        "ghostty_paste_encode", [c_char_p, c_size_t, c_bool, c_char_p, c_size_t, POINTER(c_size_t)], c_int
    )


DATA_COLS = 1
DATA_ROWS = 2
DATA_CURSOR_X = 3
DATA_CURSOR_Y = 4
DATA_ACTIVE_SCREEN = 6
DATA_CURSOR_VISIBLE = 7
DATA_KITTY_KEYBOARD_FLAGS = 8
DATA_SCROLLBAR = 9
DATA_MOUSE_TRACKING = 11
DATA_TITLE = 12
DATA_PWD = 13
DATA_TOTAL_ROWS = 14
DATA_SCROLLBACK_ROWS = 15
DATA_WIDTH_PX = 16
DATA_HEIGHT_PX = 17
DATA_COLOR_FOREGROUND = 18
DATA_COLOR_BACKGROUND = 19
DATA_COLOR_CURSOR = 20
DATA_COLOR_PALETTE = 21
DATA_VIEWPORT_ACTIVE = 32
DATA_MODE = 37

RENDER_DATA_COLS = 1
RENDER_DATA_ROWS = 2
RENDER_DATA_ROW_ITERATOR = 4
RENDER_DATA_COLORS = 19
RENDER_DATA_CURSOR = 18
RENDER_DATA_OVERSCAN = 20

ROW_DATA_CELLS = 3
ROW_DATA_VIEWPORT_Y = 6

CELLS_DATA_RAW = 1
CELLS_DATA_STYLE = 2
CELLS_DATA_GRAPHEMES_UTF8 = 9
CELLS_DATA_BG_COLOR = 5
CELLS_DATA_FG_COLOR = 6

CELL_DATA_WIDE = 3
CELL_WIDE_SPACER_TAIL = 2

OPT_USERDATA = 0
OPT_WRITE_PTY = 1
OPT_BELL = 2
OPT_TITLE_CHANGED = 5
OPT_COLOR_FOREGROUND = 11
OPT_COLOR_BACKGROUND = 12
OPT_COLOR_CURSOR = 13
OPT_COLOR_PALETTE = 14
OPT_KITTY_IMAGE_STORAGE_LIMIT = 15
OPT_PWD_CHANGED = 25
OPT_SCROLLBACK_MAX_BYTES = 27
OPT_SCROLLBACK_MAX_LINES = 28
OPT_CLIPBOARD_WRITE = 26
OPT_TERMINFO_NAME = 37

SCROLL_TOP = 0
SCROLL_BOTTOM = 1
SCROLL_DELTA = 2
SCROLL_ROW = 3

SCROLL_PACK = ScrollViewport

KEY_ACTION_PRESS = 1
KEY_ACTION_RELEASE = 0
KEY_ACTION_REPEAT = 2

MOD_SHIFT = 1 << 0
MOD_CTRL = 1 << 1
MOD_ALT = 1 << 2
MOD_SUPER = 1 << 3

MOUSE_ACTION_PRESS = 0
MOUSE_ACTION_RELEASE = 1
MOUSE_ACTION_MOTION = 2


class Terminal:
    def __init__(
        self,
        cols: int,
        rows: int,
        *,
        cell_width: int = 8,
        cell_height: int = 16,
        on_write=None,
        on_title=None,
        on_bell=None,
        on_clipboard=None,
        on_pwd=None,
        scrollback_lines: int = 10000,
        scrollback_bytes: int = 32 * 1024 * 1024,
    ):
        self.l = lib()
        self._handle = c_void_p()
        if self.l.ghostty_terminal_new(None, byref(self._handle), max(1, cols), max(1, rows)) != RESULT_SUCCESS:
            raise GhosttyError("failed to create libghostty terminal")
        self._closed = False
        self._on_write = on_write
        self._on_title = on_title
        self._on_bell = on_bell
        self._on_clipboard = on_clipboard
        self._on_pwd = on_pwd
        self._cell_width = max(1, cell_width)
        self._cell_height = max(1, cell_height)

        self._cb_write = WRITE_PTY_FN(self._write_pty)
        self._cb_bell = BELL_FN(self._bell)
        self._cb_title = TITLE_FN(self._title_changed)
        self._cb_pwd = PWD_FN(self._pwd_changed)
        self._cb_clipboard = CLIPBOARD_WRITE_FN(self._clipboard_write)
        self._set_opt(OPT_USERDATA, None)
        self._set_opt(OPT_WRITE_PTY, self._cb_write)
        self._set_opt(OPT_BELL, self._cb_bell)
        self._set_opt(OPT_TITLE_CHANGED, self._cb_title)
        self._set_opt(OPT_PWD_CHANGED, self._cb_pwd)
        self._set_opt(OPT_CLIPBOARD_WRITE, self._cb_clipboard)
        self._set_size_value(OPT_SCROLLBACK_MAX_LINES, c_size_t, scrollback_lines)
        self._set_size_value(OPT_SCROLLBACK_MAX_BYTES, c_size_t, scrollback_bytes)
        self._set_size_value(OPT_KITTY_IMAGE_STORAGE_LIMIT, c_uint64, 64 * 1024 * 1024)
        self._set_string(OPT_TERMINFO_NAME, "xterm-256color")

        self._render = c_void_p()
        if self.l.ghostty_render_state_new(None, byref(self._render)) != RESULT_SUCCESS:
            raise GhosttyError("failed to create libghostty render state")
        self._rows_iter = c_void_p()
        if (
            self.l.ghostty_render_state_row_iterator_new(None, byref(self._rows_iter))
            != RESULT_SUCCESS
        ):
            raise GhosttyError("failed to create libghostty row iterator")
        self._cells = c_void_p()
        if self.l.ghostty_render_state_row_cells_new(None, byref(self._cells)) != RESULT_SUCCESS:
            raise GhosttyError("failed to create libghostty cell iterator")

        self._key_encoder = c_void_p()
        if self.l.ghostty_key_encoder_new(None, byref(self._key_encoder)) != RESULT_SUCCESS:
            raise GhosttyError("failed to create libghostty key encoder")
        self._key_event = c_void_p()
        if self.l.ghostty_key_event_new(None, byref(self._key_event)) != RESULT_SUCCESS:
            raise GhosttyError("failed to create libghostty key event")
        self._mouse_encoder = c_void_p()
        if self.l.ghostty_mouse_encoder_new(None, byref(self._mouse_encoder)) != RESULT_SUCCESS:
            raise GhosttyError("failed to create libghostty mouse encoder")
        self._mouse_event = c_void_p()
        if self.l.ghostty_mouse_event_new(None, byref(self._mouse_event)) != RESULT_SUCCESS:
            raise GhosttyError("failed to create libghostty mouse event")

        self.resize(cols, rows, self._cell_width, self._cell_height)

    @property
    def handle(self):
        return self._handle

    def _set_opt(self, option, value):
        if isinstance(value, c_void_p):
            ptr = value
        elif value is not None and hasattr(value, "_flags_"):
            ptr = C.cast(value, c_void_p)
        else:
            ptr = value
        self.l.ghostty_terminal_set(self._handle, option, ptr)

    def _set_size_value(self, option, ctype, value):
        v = ctype(value)
        self.l.ghostty_terminal_set(self._handle, option, byref(v))

    def _set_string(self, option, value):
        raw = value.encode("utf-8")
        buf = C.create_string_buffer(raw)
        s = GhosttyString(C.cast(buf, POINTER(c_uint8)), len(raw))
        self.l.ghostty_terminal_set(self._handle, option, byref(s))

    def set_colors(self, foreground=None, background=None, cursor=None, palette=None):
        def put(option, color):
            if color is None:
                return
            c = RGB(*color)
            self.l.ghostty_terminal_set(self._handle, option, byref(c))

        put(OPT_COLOR_FOREGROUND, foreground)
        put(OPT_COLOR_BACKGROUND, background)
        put(OPT_COLOR_CURSOR, cursor)
        if palette:
            values = (RGB * 256)()
            for i in range(256):
                value = palette[i] if i < len(palette) else (0, 0, 0)
                values[i] = RGB(*value)
            self.l.ghostty_terminal_set(self._handle, OPT_COLOR_PALETTE, byref(values))

    def _write_pty(self, terminal, userdata, data, length):
        if self._on_write and data and length:
            try:
                self._on_write(bytes(data[:length]))
            except Exception as e:
                print("sublime_term: write callback failed:", e)

    def _bell(self, terminal, userdata):
        if self._on_bell:
            try:
                self._on_bell()
            except Exception:
                pass

    def _title_changed(self, terminal, userdata):
        if self._on_title:
            try:
                self._on_title(self.title())
            except Exception:
                pass

    def _pwd_changed(self, terminal, userdata):
        if self._on_pwd:
            try:
                self._on_pwd(self.pwd())
            except Exception:
                pass

    def _clipboard_write(self, terminal, userdata, write):
        try:
            if not write:
                return
            request = write.contents
            text = None
            is_clear = request.contents_len == 0
            for i in range(request.contents_len):
                content = request.contents[i]
                mime = content.mime.text()
                if mime.startswith("text/") or mime == "UTF8_STRING":
                    text = content.data.text()
                    break
            if not is_clear and text is None:
                result = 2
            else:
                result = 0
                if self._on_clipboard:
                    self._on_clipboard(text or "", is_clear)
            reply = ClipboardWriteReply()
            reply.size = C.sizeof(reply)
            reply.result = result
            reply.remember = False
            request.reply(write, byref(reply))
        except Exception as e:
            print("sublime_term: clipboard callback failed:", e)
            try:
                reply = ClipboardWriteReply()
                reply.size = C.sizeof(reply)
                reply.result = 5
                write.contents.reply(write, byref(reply))
            except Exception:
                pass

    def resize(self, cols: int, rows: int, cell_width: int, cell_height: int):
        self._cell_width = max(1, int(cell_width))
        self._cell_height = max(1, int(cell_height))
        self.l.ghostty_terminal_resize(
            self._handle,
            max(1, int(cols)),
            max(1, int(rows)),
            self._cell_width,
            self._cell_height,
        )

    def write(self, data: bytes):
        if not data or self._closed:
            return
        self.l.ghostty_terminal_vt_write(self._handle, data, len(data))

    def reset(self):
        if not self._closed:
            self.l.ghostty_terminal_reset(self._handle)

    def get(self, kind, ctype):
        value = ctype()
        result = self.l.ghostty_terminal_get(self._handle, kind, byref(value))
        return value if result == RESULT_SUCCESS else None

    def get_string(self, kind) -> str:
        value = GhosttyString()
        result = self.l.ghostty_terminal_get(self._handle, kind, byref(value))
        return value.text() if result == RESULT_SUCCESS else ""

    def title(self) -> str:
        return self.get_string(DATA_TITLE)

    def pwd(self) -> str:
        return self.get_string(DATA_PWD)

    def mode(self, mode: int, ansi: bool = False) -> bool:
        config = ModeConfig()
        config.mode = (mode & 0x7FFF) | (0x8000 if ansi else 0)
        result = self.l.ghostty_terminal_get(self._handle, DATA_MODE, byref(config))
        return bool(config.value) if result == RESULT_SUCCESS else False

    def scroll(self, delta: int):
        behavior = ScrollViewport()
        behavior.tag = SCROLL_DELTA
        behavior.value.delta = C.c_uint64(delta & 0xFFFFFFFFFFFFFFFF).value
        self.l.ghostty_terminal_scroll_viewport(self._handle, behavior)

    def scroll_to(self, where: int):
        behavior = ScrollViewport()
        behavior.tag = where
        self.l.ghostty_terminal_scroll_viewport(self._handle, behavior)

    def scroll_row(self, row: int):
        behavior = ScrollViewport()
        behavior.tag = SCROLL_ROW
        behavior.value.row = row
        self.l.ghostty_terminal_scroll_viewport(self._handle, behavior)

    def _encode_with(self, encoder, event, func):
        n = c_size_t()
        result = func(encoder, event, None, 0, byref(n))
        if result != RESULT_OUT_OF_SPACE and n.value == 0:
            return b""
        if n.value == 0:
            return b""
        buf = C.create_string_buffer(n.value)
        result = func(encoder, event, buf, n.value, byref(n))
        if result != RESULT_SUCCESS:
            return b""
        return buf.raw[: n.value]

    def key(self, key: int, mods: int = 0, text: str = "", action: int = KEY_ACTION_PRESS) -> bytes:
        self.l.ghostty_key_encoder_setopt_from_terminal(self._key_encoder, self._handle)
        self.l.ghostty_key_event_set_action(self._key_event, action)
        self.l.ghostty_key_event_set_key(self._key_event, key)
        self.l.ghostty_key_event_set_mods(self._key_event, mods)
        self.l.ghostty_key_event_set_consumed_mods(self._key_event, 0)
        raw = text.encode("utf-8") if text else None
        self.l.ghostty_key_event_set_utf8(self._key_event, raw, len(raw) if raw else 0)
        if text:
            self.l.ghostty_key_event_set_unshifted_codepoint(self._key_event, ord(text[0]))
        else:
            self.l.ghostty_key_event_set_unshifted_codepoint(self._key_event, 0)
        return self._encode_with(self._key_encoder, self._key_event, self.l.ghostty_key_encoder_encode)

    def mouse(
        self,
        action: int,
        button: int,
        x: float,
        y: float,
        mods: int = 0,
        screen_width: int = 1,
        screen_height: int = 1,
        cell_width: int = 8,
        cell_height: int = 16,
        any_pressed: bool = False,
    ) -> bytes:
        self.l.ghostty_mouse_encoder_setopt_from_terminal(self._mouse_encoder, self._handle)
        size = MouseEncoderSize()
        size.size = C.sizeof(size)
        size.screen_width = max(1, int(screen_width))
        size.screen_height = max(1, int(screen_height))
        size.cell_width = max(1, int(cell_width))
        size.cell_height = max(1, int(cell_height))
        self.l.ghostty_mouse_encoder_setopt(self._mouse_encoder, 2, byref(size))
        pressed = c_bool(any_pressed)
        self.l.ghostty_mouse_encoder_setopt(self._mouse_encoder, 3, byref(pressed))
        self.l.ghostty_mouse_event_set_action(self._mouse_event, action)
        if button:
            self.l.ghostty_mouse_event_set_button(self._mouse_event, button)
        else:
            self.l.ghostty_mouse_event_clear_button(self._mouse_event)
        self.l.ghostty_mouse_event_set_mods(self._mouse_event, mods)
        self.l.ghostty_mouse_event_set_position(self._mouse_event, MousePosition(x, y))
        return self._encode_with(
            self._mouse_encoder, self._mouse_event, self.l.ghostty_mouse_encoder_encode
        )

    def paste(self, data: bytes) -> bytes:
        bracketed = self.mode(2004)
        source = C.create_string_buffer(data)
        n = c_size_t()
        result = self.l.ghostty_paste_encode(
            C.cast(source, c_char_p), len(data), bracketed, None, 0, byref(n)
        )
        if n.value == 0:
            return b""
        out = C.create_string_buffer(n.value)
        result = self.l.ghostty_paste_encode(
            C.cast(source, c_char_p), len(data), bracketed, out, n.value, byref(n)
        )
        if result != RESULT_SUCCESS:
            return b""
        return out.raw[: n.value]

    def read_screen(self) -> Screen:
        l = self.l
        screen = Screen()
        cols = self.get(RENDER_DATA_COLS, c_uint16)
        rows = self.get(RENDER_DATA_ROWS, c_uint16)
        screen.cols = cols.value if cols else 0
        screen.rows = rows.value if rows else 0
        colors = Colors()
        colors.size = C.sizeof(colors)
        if l.ghostty_render_state_get(self._render, RENDER_DATA_COLORS, byref(colors)) == RESULT_SUCCESS:
            screen.colors = colors
        cursor = Cursor()
        cursor.size = C.sizeof(cursor)
        if l.ghostty_render_state_get(self._render, RENDER_DATA_CURSOR, byref(cursor)) == RESULT_SUCCESS:
            screen.cursor = cursor
        scrollbar = self.get(DATA_SCROLLBAR, Scrollbar)
        screen.scrollbar = scrollbar
        tracking = self.get(DATA_MOUSE_TRACKING, c_bool)
        screen.mouse = bool(tracking.value) if tracking else False
        active = self.get(DATA_ACTIVE_SCREEN, c_int)
        screen.active_screen = active.value if active else 0
        screen.title = self.title()
        screen.pwd = self.pwd()

        lines = []
        iter_ok = l.ghostty_render_state_get(
            self._render, RENDER_DATA_ROW_ITERATOR, byref(self._rows_iter)
        )
        if iter_ok != RESULT_SUCCESS:
            screen.lines = lines
            return screen

        text_buf = C.create_string_buffer(256)
        while l.ghostty_render_state_row_iterator_next(self._rows_iter):
            if (
                l.ghostty_render_state_row_get(self._rows_iter, ROW_DATA_CELLS, byref(self._cells))
                != RESULT_SUCCESS
            ):
                lines.append([])
                continue
            row = []
            while l.ghostty_render_state_row_cells_next(self._cells):
                cell = CellData()
                buf = GhosttyBuffer(C.cast(text_buf, POINTER(c_uint8)), 256, 0)
                result = l.ghostty_render_state_row_cells_get(
                    self._cells, CELLS_DATA_GRAPHEMES_UTF8, byref(buf)
                )
                if result == RESULT_OUT_OF_SPACE:
                    required = max(1, buf.len)
                    dynamic = C.create_string_buffer(required)
                    buf = GhosttyBuffer(C.cast(dynamic, POINTER(c_uint8)), required, 0)
                    result = l.ghostty_render_state_row_cells_get(
                        self._cells, CELLS_DATA_GRAPHEMES_UTF8, byref(buf)
                    )
                    raw = dynamic.raw[: buf.len]
                else:
                    raw = text_buf.raw[: buf.len]
                if result == RESULT_SUCCESS and buf.len:
                    cell.text = raw.decode("utf-8", "replace")

                raw_cell = c_uint64()
                if (
                    l.ghostty_render_state_row_cells_get(
                        self._cells, CELLS_DATA_RAW, byref(raw_cell)
                    )
                    == RESULT_SUCCESS
                ):
                    wide = c_int()
                    if (
                        l.ghostty_cell_get(raw_cell.value, CELL_DATA_WIDE, byref(wide))
                        == RESULT_SUCCESS
                        and wide.value == CELL_WIDE_SPACER_TAIL
                    ):
                        cell.tail = True

                style = Style()
                style.size = C.sizeof(style)
                if (
                    l.ghostty_render_state_row_cells_get(
                        self._cells, CELLS_DATA_STYLE, byref(style)
                    )
                    == RESULT_SUCCESS
                ):
                    cell.bold = bool(style.bold)
                    cell.italic = bool(style.italic)
                    cell.faint = bool(style.faint)
                    cell.blink = bool(style.blink)
                    cell.inverse = bool(style.inverse)
                    cell.invisible = bool(style.invisible)
                    cell.strikethrough = bool(style.strikethrough)
                    cell.overline = bool(style.overline)
                    cell.underline = style.underline
                    if style.underline_color.tag == 2:
                        cell.underline_color = style.underline_color.value.rgb.tuple()

                fg = RGB()
                if (
                    l.ghostty_render_state_row_cells_get(
                        self._cells, CELLS_DATA_FG_COLOR, byref(fg)
                    )
                    == RESULT_SUCCESS
                ):
                    cell.fg = fg.tuple()
                bg = RGB()
                if (
                    l.ghostty_render_state_row_cells_get(
                        self._cells, CELLS_DATA_BG_COLOR, byref(bg)
                    )
                    == RESULT_SUCCESS
                ):
                    cell.bg = bg.tuple()
                row.append(cell)
            lines.append(row)
        screen.lines = lines
        l.ghostty_render_state_clean(self._render)
        return screen

    def update(self):
        if not self._closed:
            self.l.ghostty_render_state_update(self._render, self._handle)

    def close(self):
        if self._closed:
            return
        self._closed = True
        l = self.l
        l.ghostty_mouse_event_free(self._mouse_event)
        l.ghostty_mouse_encoder_free(self._mouse_encoder)
        l.ghostty_key_event_free(self._key_event)
        l.ghostty_key_encoder_free(self._key_encoder)
        l.ghostty_render_state_row_cells_free(self._cells)
        l.ghostty_render_state_row_iterator_free(self._rows_iter)
        l.ghostty_render_state_free(self._render)
        l.ghostty_terminal_free(self._handle)
        self._handle = c_void_p()


def available() -> bool:
    try:
        lib()
        return True
    except GhosttyError:
        return False
