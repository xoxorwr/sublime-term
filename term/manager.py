from __future__ import annotations

import sublime

from .session import TerminalSession

_sessions = {}
_scheduled = False
_minimap_visible = {}
PANEL_NAME = "sublime_term"


def get(view_id):
    return _sessions.get(view_id)


def all_sessions():
    return list(_sessions.values())


def create(window: sublime.Window, options=None):
    hide_minimap(window)
    view = window.new_file()
    try:
        session = TerminalSession(window, view, options or {})
    except Exception as e:
        view.close()
        if not any(s.window.id() == window.id() for s in _sessions.values()):
            restore_minimap(window)
        sublime.error_message("Sublime Term: {}\n\nSee the console for details.".format(e))
        print("sublime_term: failed to create terminal:", e)
        import traceback

        traceback.print_exc()
        return None
    _sessions[view.id()] = session
    _ensure_timer()
    window.focus_view(view)
    hide_minimap(window)
    sublime.set_timeout(lambda: hide_minimap(window), 50)
    sublime.set_timeout(lambda: session.refresh_size(force=True), 50)
    return session


def find_panel(window):
    view = window.find_output_panel(PANEL_NAME)
    if view:
        return _sessions.get(view.id())
    return None


def create_panel(window: sublime.Window, options=None):
    view = window.find_output_panel(PANEL_NAME)
    if view is None:
        view = window.create_output_panel(PANEL_NAME)
    session = _sessions.get(view.id())
    if session is None:
        try:
            session = TerminalSession(window, view, options or {}, panel=True)
        except Exception as e:
            window.destroy_output_panel(PANEL_NAME)
            sublime.error_message("Sublime Term: {}\n\nSee the console for details.".format(e))
            print("sublime_term: failed to create panel terminal:", e)
            import traceback

            traceback.print_exc()
            return None
        _sessions[view.id()] = session
        _ensure_timer()
    window.run_command("show_panel", {"panel": "output." + PANEL_NAME})
    window.focus_view(view)
    sublime.set_timeout(session.after_show, 50)
    return session


def toggle_panel(window: sublime.Window, options=None):
    if window.active_panel() == "output." + PANEL_NAME:
        window.run_command("hide_panel", {"panel": "output." + PANEL_NAME})
        return None
    return create_panel(window, options)


def close_panel(window: sublime.Window):
    view = window.find_output_panel(PANEL_NAME)
    if view:
        session = _sessions.pop(view.id(), None)
        if session:
            session.close()
        window.destroy_output_panel(PANEL_NAME)


def close_window(window: sublime.Window):
    if not window:
        return
    window_id = window.id()
    for session in list(_sessions.values()):
        try:
            if session.window.id() == window_id:
                _sessions.pop(session.view.id(), None)
                session.close()
        except Exception:
            pass
    _minimap_visible.pop(window_id, None)


def hide_minimap(window: sublime.Window):
    if not window or not window.is_valid():
        return
    window_id = window.id()
    try:
        if window_id not in _minimap_visible:
            _minimap_visible[window_id] = window.is_minimap_visible()
        window.set_minimap_visible(False)
    except Exception:
        _minimap_visible.pop(window_id, None)


def restore_minimap(window: sublime.Window):
    if not window or not window.is_valid():
        return
    visible = _minimap_visible.pop(window.id(), None)
    if visible is not None:
        try:
            window.set_minimap_visible(visible)
        except Exception:
            pass


def remove(session, close_view=False):
    if not session:
        return
    if _sessions.get(session.view.id()) is session:
        del _sessions[session.view.id()]
    session.close()
    if close_view and session.view.is_valid():
        session.view.close()


def close_view(view):
    session = _sessions.pop(view.id(), None)
    if session:
        session.close()


def close_all():
    for session in list(_sessions.values()):
        session.close()
    _sessions.clear()


def _ensure_timer():
    global _scheduled
    if not _scheduled:
        _scheduled = True
        sublime.set_timeout(_tick, 16)


def _tick():
    global _scheduled
    for session in list(_sessions.values()):
        try:
            if not session.view.is_valid():
                _sessions.pop(session.view.id(), None)
                session.close()
                continue
            session.tick()
        except Exception as e:
            print("sublime_term: tick failed:", e)
            import traceback

            traceback.print_exc()
    if _sessions:
        sublime.set_timeout(_tick, 16)
    else:
        _scheduled = False
