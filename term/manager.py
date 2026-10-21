from __future__ import annotations

import sublime

from .session import TerminalSession

_sessions = {}
_scheduled = False


def get(view_id):
    return _sessions.get(view_id)


def all_sessions():
    return list(_sessions.values())


def create(window: sublime.Window, options=None):
    view = window.new_file()
    try:
        session = TerminalSession(window, view, options or {})
    except Exception as e:
        view.close()
        sublime.error_message("Sublime Term: {}\n\nSee the console for details.".format(e))
        print("sublime_term: failed to create terminal:", e)
        import traceback

        traceback.print_exc()
        return None
    _sessions[view.id()] = session
    _ensure_timer()
    window.focus_view(view)
    return session


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
            session.tick()
        except Exception as e:
            print("sublime_term: tick failed:", e)
            import traceback

            traceback.print_exc()
    if _sessions:
        sublime.set_timeout(_tick, 16)
    else:
        _scheduled = False
