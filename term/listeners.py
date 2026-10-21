from __future__ import annotations

import sublime
import sublime_plugin

from . import manager


_SWALLOW = {
    "undo",
    "redo",
    "soft_undo",
    "soft_redo",
    "right_delete",
    "left_delete",
    "delete_word",
    "delete_to_hard_bol",
    "delete_to_hard_eol",
    "move",
    "move_to",
    "select",
    "expand_selection",
    "toggle_comment",
    "insert_snippet",
    "run_macro_file",
}


class TerminalEventListener(sublime_plugin.EventListener):
    def on_close(self, view):
        if view.settings().get("terminal_view"):
            manager.close_view(view)

    def on_activated(self, view):
        if view.settings().get("terminal_view"):
            session = manager.get(view.id())
            if session:
                session.send_focus(True)

    def on_deactivated(self, view):
        if view.settings().get("terminal_view"):
            session = manager.get(view.id())
            if session:
                session.send_focus(False)

    def on_hover(self, view, point, hover_zone):
        if view.settings().get("terminal_view"):
            session = manager.get(view.id())
            if session:
                session.update_mouse_cell(point)

    def on_modified(self, view):
        if not view.settings().get("terminal_view"):
            return
        session = manager.get(view.id())
        if not session:
            return
        command, args, _ = view.command_history(0)
        if not command or command.startswith("terminal_"):
            return
        args = args or {}
        if command == "insert":
            text = args.get("characters", "")
            if text:
                view.run_command("terminal_absorb_key", {"chars": text})
        else:
            sublime.set_timeout(lambda: session.render() if view.is_valid() else None, 1)

    def on_text_command(self, view, name, args):
        if not view.settings().get("terminal_view"):
            return None
        args = args or {}
        session = manager.get(view.id())
        if not session:
            return None
        if name == "insert":
            text = args.get("characters", "")
            text = text.replace("\r\n", "\r").replace("\n", "\r")
            if text:
                session.send_text(text)
            return ("terminal_noop", {})
        if name in ("left_delete", "delete_word"):
            session.send_key("backspace", 0, "")
            return ("terminal_noop", {})
        if name == "right_delete":
            session.send_key("delete", 0, "")
            return ("terminal_noop", {})
        if name in ("paste", "paste_and_indent"):
            view.run_command("terminal_paste")
            return ("terminal_noop", {})
        if name == "paste_selection_clipboard":
            view.run_command("terminal_paste_selection")
            return ("terminal_noop", {})
        if name in ("copy", "cut"):
            session.copy_selection()
            return ("terminal_noop", {})
        if name in _SWALLOW:
            return ("terminal_noop", {})
        return None
