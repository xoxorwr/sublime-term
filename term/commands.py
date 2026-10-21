from __future__ import annotations

import os
import sublime
import sublime_plugin

from . import ghostty, keys, manager
from . import theme as term_theme


def _session(view):
    return manager.get(view.id())


def _window_cwd(window):
    variables = window.extract_variables()
    file_path = variables.get("file")
    if file_path:
        folder = os.path.dirname(file_path)
        if os.path.isdir(folder):
            return folder
    folder = variables.get("folder")
    if folder and os.path.isdir(folder):
        return folder
    folders = window.folders()
    if folders and os.path.isdir(folders[0]):
        return folders[0]
    return os.getcwd()


def _expand(window, value):
    if not value:
        return value
    try:
        return sublime.expand_variables(value, window.extract_variables())
    except Exception:
        return value


class TerminalOpenCommand(sublime_plugin.WindowCommand):
    def run(self, cwd=None, command=None, title=None, shell=None, argv=None):
        options = {}
        if cwd:
            options["cwd"] = _expand(self.window, cwd)
        else:
            options["cwd"] = _window_cwd(self.window)
        if command:
            options["command"] = command
            options["title"] = title or command
        if title:
            options["title"] = title
        if shell:
            options["shell"] = shell
        if argv:
            options["argv"] = argv
        manager.create(self.window, options)

    def is_enabled(self):
        return ghostty.available()


class TerminalTogglePanelCommand(sublime_plugin.WindowCommand):
    def run(self, cwd=None):
        options = {"cwd": _expand(self.window, cwd) if cwd else _window_cwd(self.window)}
        manager.toggle_panel(self.window, options)

    def is_enabled(self):
        return ghostty.available()


class TerminalClosePanelCommand(sublime_plugin.WindowCommand):
    def run(self):
        manager.close_panel(self.window)


class TerminalOpenHereCommand(sublime_plugin.WindowCommand):
    def run(self):
        manager.create(self.window, {"cwd": _window_cwd(self.window)})

    def is_enabled(self):
        return ghostty.available()


class TerminalRunCommand(sublime_plugin.WindowCommand):
    def run(self, cwd=None):
        cwd = _expand(self.window, cwd) if cwd else _window_cwd(self.window)
        view = self.window.active_view()
        initial = ""
        if view and view.sel():
            initial = view.substr(view.sel()[0]).strip()

        def done(command):
            if command:
                manager.create(self.window, {"cwd": cwd, "command": command, "title": command})

        self.window.show_input_panel("Command:", initial, done, None, None)

    def is_enabled(self):
        return ghostty.available()


class TerminalRestartCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        session = _session(self.view)
        if not session:
            return
        options = {
            "cwd": session.cwd,
            "shell": session.shell,
            "command": session.command,
            "argv": session.argv,
        }
        window = session.window
        if session.is_panel:
            manager.remove(session)
            window.destroy_output_panel(manager.PANEL_NAME)
            manager.create_panel(window, options)
            return
        manager.remove(session, close_view=True)
        manager.create(window, options)


class TerminalCloseCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        session = _session(self.view)
        if not session:
            return
        if session.is_panel:
            manager.close_panel(session.window)
        else:
            manager.remove(session, close_view=True)


class TerminalCopyCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        session = _session(self.view)
        if session:
            session.copy_selection()


class TerminalPasteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        session = _session(self.view)
        if not session:
            return
        view = self.view

        def done(text):
            if text and view.is_valid():
                current = _session(view)
                if current:
                    current.send_paste(text)

        sublime.get_clipboard_async(done)


class TerminalPasteSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        session = _session(self.view)
        if not session:
            return
        try:
            import subprocess

            text = subprocess.check_output(
                ["xclip", "-o", "-selection", "primary"], stderr=subprocess.DEVNULL
            ).decode("utf-8", "replace")
        except Exception:
            text = sublime.get_clipboard()
        if text:
            session.send_paste(text)


class TerminalScrollCommand(sublime_plugin.TextCommand):
    def run(self, edit, delta=0, to=None):
        session = _session(self.view)
        if not session:
            return
        if to == "top":
            session.scroll_to(ghostty.SCROLL_TOP)
        elif to == "bottom":
            session.scroll_to(ghostty.SCROLL_BOTTOM)
        elif delta:
            session.scroll(int(delta))


class TerminalKeyCommand(sublime_plugin.TextCommand):
    def run(self, edit, key="", mods=None, text=""):
        session = _session(self.view)
        if not session:
            return
        mods_int = keys.mods_from_names(mods)
        session.send_key(key, mods_int, text)


class TerminalSendTextCommand(sublime_plugin.TextCommand):
    def run(self, edit, text=""):
        session = _session(self.view)
        if session:
            session.send_text(text)


class TerminalMouseCommand(sublime_plugin.TextCommand):
    def want_event(self):
        return True

    def run(self, edit, button=1, action="press", event=None):
        session = _session(self.view)
        tracking = self.view.settings().get("terminal_mouse_tracking")
        if not session:
            return
        if action == "press" and button in (1, 2, 3):
            window = self.view.window()
            if window:
                window.focus_view(self.view)
        if button in (4, 5):
            if not tracking:
                session.scroll(-3 if button == 4 else 3)
                return
            if event:
                try:
                    session.update_mouse_cell(
                        self.view.window_to_text((event["x"], event["y"]))
                    )
                except Exception:
                    pass
            grid_x, row = session.last_mouse_cell
            session.send_mouse(ghostty.MOUSE_ACTION_PRESS, button, grid_x, row, 0)
            return
        if not tracking or not event:
            return
        try:
            point = self.view.window_to_text((event["x"], event["y"]))
        except Exception:
            return
        grid_x, row = session.mouse_cell(point)
        session.last_mouse_cell = (grid_x, row)
        mods = keys.mods_from_names(event.get("modifiers"))
        act = {
            "press": ghostty.MOUSE_ACTION_PRESS,
            "release": ghostty.MOUSE_ACTION_RELEASE,
            "motion": ghostty.MOUSE_ACTION_MOTION,
        }.get(action, ghostty.MOUSE_ACTION_PRESS)
        session.send_mouse(act, button, grid_x, row, mods)


class TerminalOpenPathCommand(sublime_plugin.TextCommand):
    def want_event(self):
        return True

    def run(self, edit, event=None):
        session = _session(self.view)
        if not session or not event:
            return
        try:
            point = self.view.window_to_text((event["x"], event["y"]))
        except Exception:
            return
        window = self.view.window()
        if window:
            window.focus_view(self.view)
        session.open_path_at_point(point)


class TerminalRenderCommand(sublime_plugin.TextCommand):
    def run(self, edit, session_id=0):
        session = manager.get(session_id)
        if session:
            session.apply_frame(self.view, edit)


class TerminalAbsorbKeyCommand(sublime_plugin.TextCommand):
    def run(self, edit, chars=""):
        session = _session(self.view)
        if not session:
            return
        region = None
        selections = self.view.sel()
        if len(selections) == 1 and selections[0].empty():
            end = selections[0].b
            start = max(0, end - len(chars))
            candidate = sublime.Region(start, end)
            if self.view.substr(candidate) == chars:
                region = candidate
        if region is not None:
            self.view.erase(edit, region)
        text = chars.replace("\r\n", "\r").replace("\n", "\r")
        session.send_text(text)
        sublime.set_timeout(lambda: session.render() if self.view.is_valid() else None, 1)


class TerminalNoopCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        pass


class TerminalClearScrollbackCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        session = _session(self.view)
        if session:
            session.clear_scrollback()


class TerminalSyncColorSchemeCommand(sublime_plugin.WindowCommand):
    def run(self):
        try:
            info = sublime.ui_info()
            term_theme.sync_to_theme(info)
            for session in manager.all_sessions():
                session.apply_theme_palette()
            sublime.status_message("Terminal: color scheme synced with current theme")
        except Exception as e:
            sublime.error_message("Sublime Term: could not sync color scheme: {}".format(e))
            import traceback

            traceback.print_exc()


class TerminalOpenSettingsCommand(sublime_plugin.WindowCommand):
    def run(self):
        self.window.run_command(
            "open_file",
            {"file": "Packages/sublime_term/sublime_term.sublime-settings"},
        )


