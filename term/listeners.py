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
    def on_query_context(self, view, key, operator, operand, match_all):
        if key != "sublime_term.keys":
            return None
        window = view.window()
        if not window:
            return False
        panel = window.active_panel()
        if panel and panel != "output.sublime_term":
            return False
        return True

    def on_pre_close_window(self, window):
        manager.close_window(window)

    def on_close(self, view):
        if view.settings().get("terminal_view"):
            manager.close_view(view)

    def on_activated(self, view):
        if view.settings().get("terminal_view"):
            session = manager.get(view.id())
            if session:
                window = view.window()
                if window:
                    manager.hide_minimap(window)
                session.send_focus(True)
                sublime.set_timeout(
                    lambda: session.refresh_size(force=True) if not session.closed else None,
                    50,
                )
        else:
            window = view.window()
            if window:
                manager.restore_minimap(window)

    def on_selection_modified(self, view):
        if not view.settings().get("terminal_view"):
            return
        session = manager.get(view.id())
        if not session:
            return
        selections = view.sel()
        if len(selections) == 1 and not selections[0].empty():
            selection = selections[0]
            head = selection.b - 1 if selection.b > selection.a else selection.b
            session.update_drag(selection.a, head)

    def on_deactivated(self, view):
        if view.settings().get("terminal_view"):
            session = manager.get(view.id())
            if session:
                session.send_focus(False)
                session.clear_hover()

    def on_hover(self, view, point, hover_zone):
        if view.settings().get("terminal_view"):
            session = manager.get(view.id())
            if session:
                session.update_hover(point)
                session.update_right_hover(point)

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
        if name == "drag_select":
            window = view.window()
            if window:
                window.focus_view(view)
            event = args.get("event")
            if event and event.get("button") == 1:
                if view.settings().get("terminal_mouse_tracking"):
                    try:
                        point = view.window_to_text((event["x"], event["y"]))
                    except Exception:
                        point = None
                    if point is not None:
                        was_drag = session._drag_active
                        session.finish_drag(point)
                        if not was_drag:
                            session.register_click(event, point)
                else:
                    session.register_click(event)
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
