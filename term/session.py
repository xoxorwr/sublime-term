from __future__ import annotations

import os
import queue
import re
import shutil
import sublime

from . import ghostty, keys
from .pty import PtyProcess
from .render import Renderer
from .theme import manager as theme_manager

VERSION = "1.0.0"
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _rgb(value, fallback):
    if isinstance(value, (tuple, list)) and len(value) == 3:
        return tuple(max(0, min(255, int(v))) for v in value)
    if not value or not isinstance(value, str):
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


def _clean_title(title: str) -> str:
    title = CONTROL_RE.sub("", title or "").strip()
    return title[:120]


class TerminalSession:
    def __init__(self, window, view, options):
        self.window = window
        self.view = view
        self.options = options or {}
        self.settings = sublime.load_settings("sublime_term.sublime-settings")
        self.cwd = self.options.get("cwd") or self._default_cwd()
        self.shell = self.options.get("shell") or self.settings.get("shell") or os.environ.get("SHELL") or "/bin/bash"
        self.command = self.options.get("command")
        self.argv = self.options.get("argv")
        self.title = self.options.get("title") or "Terminal"
        self.pid = None
        self.pty = None
        self.terminal = None
        self.renderer = Renderer()
        self.pending_frame = None
        self.exited = False
        self.closed = False
        self.cols = 0
        self.rows = 0
        self._tick_count = 0
        self._last_title = ""
        self._last_scroll_status = ""
        self._last_mouse = None
        self._mouse_buttons = set()
        self.last_mouse_cell = (0, 0)
        self._theme = self._theme_from_settings()

        self._configure_view()
        self._create_terminal()
        self._start_pty()
        self.refresh_size(force=True)
        self.render()

    def _default_cwd(self):
        variables = self.window.extract_variables()
        folder = variables.get("folder")
        if folder and os.path.isdir(folder):
            return folder
        file_path = variables.get("file_path")
        if file_path and os.path.isdir(file_path):
            return file_path
        return os.getcwd()

    def _theme_from_settings(self):
        fg = _rgb(self.settings.get("foreground"), (216, 222, 233))
        bg = _rgb(self.settings.get("background"), (30, 30, 30))
        cursor = _rgb(self.settings.get("cursor"), fg)
        selection = _rgb(self.settings.get("selection"), (59, 66, 82))
        selection_fg = _rgb(self.settings.get("selection_foreground"), (236, 239, 244))
        palette = self.settings.get("palette")
        return {
            "foreground": fg,
            "background": bg,
            "cursor": cursor,
            "selection": selection,
            "selection_foreground": selection_fg,
            "palette": palette,
        }

    def _configure_view(self):
        view = self.view
        settings = view.settings()
        view.set_scratch(True)
        view.set_read_only(False)
        view.set_name(self.title)
        view.assign_syntax("Packages/sublime_term/Terminal.sublime-syntax")
        values = {
            "terminal_view": True,
            "terminal_mouse_tracking": False,
            "word_wrap": False,
            "wrap_width": 0,
            "line_numbers": False,
            "gutter": False,
            "fold_buttons": False,
            "folding": False,
            "highlight_line": False,
            "draw_white_space": "none",
            "draw_indent_guides": False,
            "spell_check": False,
            "auto_complete": False,
            "auto_complete_with_fields": False,
            "rulers": [],
            "scroll_past_end": False,
            "scroll_bars": "hidden",
            "line_padding_top": 0,
            "line_padding_bottom": 0,
            "margin": 4,
            "caret_style": "solid",
            "caret_extra_top": 0,
            "caret_extra_bottom": 0,
            "selection_border_width": 0,
            "translate_tabs_to_spaces": False,
            "tab_size": 1,
            "show_definitions": False,
            "mini_diff": False,
            "show_encoding": False,
            "show_line_endings": False,
            "highlight_gutter": False,
            "highlight_line_number": False,
            "indent_guide_options": [],
            "font_face": self.settings.get("font_face") or "monospace",
            "font_size": self.settings.get("font_size") or 12,
            "line_height": self.settings.get("line_height") or 1.0,
        }
        for key, value in values.items():
            settings.set(key, value)
        theme = theme_manager()
        theme.configure(
            {
                "foreground": "#{:02x}{:02x}{:02x}".format(*self._theme["foreground"]),
                "background": "#{:02x}{:02x}{:02x}".format(*self._theme["background"]),
                "cursor": "#{:02x}{:02x}{:02x}".format(*self._theme["cursor"]),
                "selection": "#{:02x}{:02x}{:02x}".format(*self._theme["selection"]),
                "selection_foreground": "#{:02x}{:02x}{:02x}".format(
                    *self._theme["selection_foreground"]
                ),
            }
        )
        theme.apply(view)
        self.renderer.set_theme(
            self._theme["foreground"], self._theme["background"], self._theme["cursor"]
        )

    def _create_terminal(self):
        self.cols, self.rows = self._measure()
        self.terminal = ghostty.Terminal(
            self.cols,
            self.rows,
            cell_width=self._cell_width(),
            cell_height=self._cell_height(),
            on_write=self._write_pty,
            on_title=self._on_title,
            on_bell=self._on_bell,
            on_clipboard=self._on_clipboard,
            on_pwd=self._on_pwd,
            scrollback_lines=self.settings.get("scrollback_lines") or 10000,
            scrollback_bytes=self.settings.get("scrollback_bytes") or 32 * 1024 * 1024,
        )
        self.terminal.set_colors(
            foreground=self._theme["foreground"],
            background=self._theme["background"],
            cursor=self._theme["cursor"],
            palette=self._theme.get("palette"),
        )

    def _start_pty(self):
        env = {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "TERM_PROGRAM": "sublime_term",
            "TERM_PROGRAM_VERSION": VERSION,
        }
        shell = shutil.which(self.shell.split()[0]) if self.shell else None
        if shell:
            self.shell = shell
        argv = self.argv
        if argv:
            exe = shutil.which(argv[0]) or argv[0]
            argv = [exe] + list(argv[1:])
        self.pty = PtyProcess(self.shell, self.cwd, argv=argv, env=env)
        self.pty.start(self.cols, self.rows)
        self.pid = self.pty.pid
        if self.command and not argv:
            sublime.set_timeout(self._send_startup_command, 120)

    def _send_startup_command(self):
        if self.closed or not self.terminal:
            return
        data = self.command
        if isinstance(data, (list, tuple)):
            data = " ".join(str(x) for x in data)
        self.pty.write((str(data) + "\r").encode("utf-8"))

    def _measure(self):
        try:
            width, height = self.view.viewport_extent()
            em = self.view.em_width()
            lh = self.view.line_height()
        except Exception:
            width = height = 0
            em = lh = 0
        if width < 20 or height < 20 or em <= 0 or lh <= 0:
            return 80, 24
        cols = max(20, int((width - 8) / em))
        rows = max(5, int((height - 6) / lh))
        return cols, rows

    def _cell_width(self):
        try:
            return max(1, int(round(self.view.em_width() or 8)))
        except Exception:
            return 8

    def _cell_height(self):
        try:
            return max(1, int(round(self.view.line_height() or 16)))
        except Exception:
            return 16

    def refresh_size(self, force=False):
        if self.closed or not self.terminal:
            return False
        cols, rows = self._measure()
        if force or cols != self.cols or rows != self.rows:
            self.cols, self.rows = cols, rows
            self.terminal.resize(cols, rows, self._cell_width(), self._cell_height())
            if self.pty:
                self.pty.resize(cols, rows)
            return True
        return False

    def _write_pty(self, data):
        if self.pty and not self.closed:
            self.pty.write(data)

    def _on_title(self, title):
        self.title = _clean_title(title) or "Terminal"

    def _on_bell(self):
        sublime.status_message("Terminal bell")

    def _on_clipboard(self, text, clear):
        sublime.set_clipboard("" if clear else text)
        if not clear:
            sublime.status_message("Terminal: clipboard updated")

    def _on_pwd(self, pwd):
        pass

    def tick(self):
        if self.closed or not self.pty or not self.terminal:
            return
        self._tick_count += 1
        dirty = False
        while True:
            try:
                item = self.pty.output.get_nowait()
            except queue.Empty:
                break
            except AttributeError:
                break
            if item is None:
                self.exited = True
                self.pty.alive = False
                self.view.set_status("sublime_term_process", "exited")
                continue
            self.terminal.write(item)
            dirty = True
        if self._tick_count % 12 == 0:
            if self.refresh_size():
                dirty = True
        if dirty:
            self.render()
        self._update_scroll_status()

    def render(self):
        if self.closed or not self.terminal:
            return
        self.terminal.update()
        screen = self.terminal.read_screen()
        if screen.mouse != self._last_mouse:
            self._last_mouse = screen.mouse
            self.view.settings().set("terminal_mouse_tracking", screen.mouse)
        title = _clean_title(screen.title) or "Terminal"
        if title != self._last_title:
            self._last_title = title
            self.view.set_name(title)
        frame = self.renderer.build(screen)
        self.pending_frame = frame
        self.view.run_command("terminal_render", {"session_id": self.view.id()})

    def apply_frame(self, view, edit):
        if self.pending_frame is not None and not self.closed:
            self.renderer.apply(view, edit, self.pending_frame)

    def scroll(self, delta):
        if self.closed or not self.terminal:
            return
        self.terminal.scroll(delta)
        self.terminal.update()
        self.render()

    def scroll_to(self, where):
        if self.closed or not self.terminal:
            return
        self.terminal.scroll_to(where)
        self.terminal.update()
        self.render()

    def scroll_row(self, row):
        if self.closed or not self.terminal:
            return
        self.terminal.scroll_row(row)
        self.terminal.update()
        self.render()

    def _update_scroll_status(self):
        try:
            scroll = self.terminal.get(ghostty.DATA_SCROLLBAR, ghostty.Scrollbar)
        except Exception:
            return
        if not scroll:
            return
        if scroll.total <= scroll.len or scroll.offset >= scroll.total - scroll.len:
            text = ""
        else:
            text = "{} / {}".format(scroll.offset, max(0, scroll.total - scroll.len))
        if text != self._last_scroll_status:
            self._last_scroll_status = text
            self.view.set_status("sublime_term_scroll", text)

    def send(self, data: bytes, scroll=True):
        if self.closed or not data or not self.terminal:
            return
        if scroll:
            self.terminal.scroll_to(ghostty.SCROLL_BOTTOM)
        if self.pty:
            self.pty.write(data)

    def send_text(self, text: str):
        self.send(text.encode("utf-8"))

    def send_key(self, key: str, mods=0, text: str = ""):
        data = keys.encode(self.terminal, key, mods, text)
        self.send(data)

    def send_paste(self, text: str):
        if not self.terminal:
            return
        data = self.terminal.paste(text.encode("utf-8"))
        self.send(data)

    def mouse_cell(self, point):
        row, col = self.view.rowcol(point)
        frame = self.pending_frame
        if not frame or not frame.lines:
            return (0, 0)
        row = max(0, min(row, len(frame.lines) - 1))
        line = frame.lines[row]
        if line.text_to_cell:
            col = max(0, min(col, len(line.text_to_cell) - 1))
            grid_x = line.text_to_cell[col]
        else:
            grid_x = 0
        return (grid_x, row)

    def update_mouse_cell(self, point):
        self.last_mouse_cell = self.mouse_cell(point)

    def send_mouse(self, action, button, x, y, mods=0):
        if not self.terminal or not self._last_mouse:
            return
        if action == ghostty.MOUSE_ACTION_PRESS and button in (1, 2, 3):
            self._mouse_buttons.add(button)
        elif action == ghostty.MOUSE_ACTION_RELEASE:
            self._mouse_buttons.discard(button)
        try:
            width, height = self.view.viewport_extent()
        except Exception:
            width, height = 1, 1
        cw = self._cell_width()
        ch = self._cell_height()
        px = (x + 0.5) * cw
        py = (y + 0.5) * ch
        data = self.terminal.mouse(
            action,
            button,
            px,
            py,
            mods,
            width,
            height,
            cw,
            ch,
            any_pressed=bool(self._mouse_buttons),
        )
        if data:
            self.send(data, scroll=False)

    def send_focus(self, focused: bool):
        if self.closed or not self.terminal:
            return
        if self.terminal.mode(1004):
            self.send(b"\x1b[I" if focused else b"\x1b[O", scroll=False)

    def clear_scrollback(self):
        if self.closed or not self.terminal:
            return
        self.terminal.write(b"\x1b[3J")
        self.render()

    def reset(self):
        if self.closed or not self.terminal:
            return
        self.terminal.reset()
        self.render()

    def copy_selection(self):
        selections = self.view.sel()
        if not selections or all(sel.empty() for sel in selections):
            sublime.status_message("Terminal: nothing selected")
            return
        chunks = []
        for sel in selections:
            text = self.view.substr(sel)
            lines = [line.rstrip() for line in text.split("\n")]
            chunks.append("\n".join(lines))
        sublime.set_clipboard("\n".join(chunks))
        sublime.status_message("Terminal: copied")

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.pty:
            self.pty.close()
            self.pty = None
        if self.terminal:
            self.terminal.close()
            self.terminal = None
        try:
            self.view.settings().set("terminal_view", False)
            self.view.settings().set("terminal_mouse_tracking", False)
        except Exception:
            pass
