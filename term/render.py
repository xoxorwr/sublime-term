from __future__ import annotations

import sublime

from . import theme as term_theme


class RenderedLine:
    __slots__ = ("text", "spans", "underlines", "cursor_span", "text_to_cell")

    def __init__(self, text="", spans=None, underlines=None, cursor_span=None, text_to_cell=None):
        self.text = text
        self.spans = spans or []
        self.underlines = underlines or []
        self.cursor_span = cursor_span
        self.text_to_cell = text_to_cell or []


class Frame:
    __slots__ = ("lines", "cursor_line")

    def __init__(self):
        self.lines = []
        self.cursor_line = -1


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def _lighten(rgb, amount=0.25):
    return tuple(_clamp(v + (255 - v) * amount) for v in rgb)


def _blend(a, b, amount=0.5):
    return tuple(_clamp(a[i] * (1.0 - amount) + b[i] * amount) for i in range(3))


class Renderer:
    def __init__(self):
        self.last_texts = []
        self.region_keys = []
        self.underline_keys = []
        self.history = []
        self.history_applied = 0
        self.history_visible = True
        self.history_region_keys = []
        self._history_seq = 0
        self._history_reset = False
        self.default_fg = (216, 222, 233)
        self.default_bg = (30, 30, 30)
        self.cursor_color = (216, 222, 233)

    def set_theme(self, foreground, background, cursor):
        self.default_fg = foreground
        self.default_bg = background
        self.cursor_color = cursor

    def build(self, screen) -> Frame:
        if screen.colors:
            self.default_fg = screen.colors.foreground.tuple()
            self.default_bg = screen.colors.background.tuple()
            if screen.colors.cursor_has_value:
                self.cursor_color = screen.colors.cursor.tuple()
        cursor = screen.cursor
        cursor_x = -1
        cursor_y = -1
        if cursor and cursor.viewport_has_value and cursor.visible:
            cursor_x = int(cursor.viewport_x)
            cursor_y = int(cursor.viewport_y)
        return self.build_rows(screen.lines[: screen.rows], cursor_x, cursor_y)

    def build_rows(self, rows, cursor_x=-1, cursor_y=-1) -> Frame:
        frame = Frame()
        frame.cursor_line = cursor_y if 0 <= cursor_y < len(rows) else -1
        for y, row in enumerate(rows):
            frame.lines.append(self._build_line(row, y, cursor_x, cursor_y))
        if not frame.lines:
            frame.lines.append(RenderedLine())
        return frame

    def _build_line(self, row, y, cursor_x, cursor_y) -> RenderedLine:
        fg_default = self.default_fg
        bg_default = self.default_bg
        cursor_default = self.cursor_color
        line = RenderedLine()
        parts = []
        spans = []
        underlines = []
        grid_to_span = {}
        text_to_cell = []
        text_len = 0
        current = None
        current_underline = None
        x = 0
        n = len(row)
        while x < n:
            cell = row[x]
            if cell.tail:
                if x in grid_to_span:
                    pass
                elif grid_to_span:
                    grid_to_span[x] = grid_to_span.get(x - 1, (max(0, text_len - 1), text_len))
                x += 1
                continue
            width = 2 if x + 1 < n and row[x + 1].tail else 1
            text = cell.text if cell.text else " "
            start = text_len
            parts.append(text)
            text_len += len(text)
            end = text_len
            text_to_cell.extend([x] * len(text))
            for gx in range(x, min(x + width, max(n, 1))):
                grid_to_span[gx] = (start, end)

            fg = cell.fg if cell.fg is not None else fg_default
            bg = cell.bg if cell.bg is not None else bg_default
            if cell.inverse:
                fg, bg = bg, fg
            if cell.bold:
                fg = _lighten(fg, 0.22)
            if cell.faint:
                fg = _blend(fg, bg, 0.55)
            if cell.invisible:
                fg = bg
            is_cursor_cell = y == cursor_y and x <= cursor_x < x + width
            if is_cursor_cell:
                fg, bg = bg_default, cursor_default

            pair = (term_theme.quantize(fg), term_theme.quantize(bg))
            if current is not None and current[2] == pair and current[1] == start:
                current = (current[0], end, pair)
                spans[-1] = current
            else:
                current = (start, end, pair)
                spans.append(current)

            if cell.underline:
                color = term_theme.quantize(cell.underline_color or fg)
                if current_underline is not None and current_underline[2] == color and current_underline[1] == start:
                    current_underline = (current_underline[0], end, color)
                    underlines[-1] = current_underline
                else:
                    current_underline = (start, end, color)
                    underlines.append(current_underline)
            else:
                current_underline = None
            x += width

        for gx in range(max(n, 1)):
            grid_to_span.setdefault(gx, (max(0, text_len - 1), text_len))
        line.text = "".join(parts)
        line.spans = spans
        line.underlines = [u for u in underlines if u[1] > u[0]]
        cursor_span = grid_to_span.get(max(0, min(cursor_x, max(n, 1) - 1))) if cursor_x >= 0 else None
        line.cursor_span = cursor_span
        line.text_to_cell = text_to_cell
        return line

    def add_history(self, lines):
        if lines:
            self.history.extend(lines)

    def clear_history(self):
        self.history = []
        self.history_applied = 0
        self._history_reset = True

    def set_history_visible(self, visible):
        if self.history_visible == visible:
            return False
        self.history_visible = visible
        self.history_applied = 0
        self._history_reset = True
        return True

    def repaint_history(self, view: sublime.View):
        if not self.history_visible:
            return
        self._erase_history_regions(view)
        self._add_history_regions(view, 0, len(self.history))

    def _erase_history_regions(self, view: sublime.View):
        for key in self.history_region_keys:
            try:
                view.erase_regions(key)
            except Exception:
                pass
        self.history_region_keys = []

    def _add_history_regions(self, view: sublime.View, start: int, stop: int):
        if not self.history_visible or stop <= start:
            return
        grouped = {}
        under_grouped = {}
        for i in range(start, stop):
            line = self.history[i]
            if not line.text:
                continue
            for a, b, pair in line.spans:
                if pair[0] == self.default_fg and pair[1] == self.default_bg:
                    continue
                scope = term_theme.scope(pair[0], pair[1])
                begin = view.text_point(i, a)
                end = view.text_point(i, b)
                if end > begin:
                    grouped.setdefault(scope, []).append(sublime.Region(begin, end))
            for a, b, color in line.underlines:
                scope = term_theme.underline_scope(color)
                begin = view.text_point(i, a)
                end = view.text_point(i, b)
                if end > begin:
                    under_grouped.setdefault(scope, []).append(sublime.Region(begin, end))

        term_theme.apply(view)
        batch = self._history_seq
        self._history_seq += 1
        for index, (scope, regions) in enumerate(grouped.items()):
            key = "sublime_term_hist_color_{}_{}".format(batch, index)
            view.add_regions(key, regions, scope)
            self.history_region_keys.append(key)
        flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE
        for index, (scope, regions) in enumerate(under_grouped.items()):
            key = "sublime_term_hist_underline_{}_{}".format(batch, index)
            view.add_regions(key, regions, scope, flags=flags)
            self.history_region_keys.append(key)

    def apply(self, view: sublime.View, edit, frame: Frame):
        if not view.is_valid():
            return 0
        texts = [line.text for line in frame.lines]
        history = self.history if self.history_visible else []
        expected = self.history_applied + len(self.last_texts)
        actual = view.rowcol(view.size())[0] + 1
        force = self._history_reset or view.size() == 0 or actual != expected
        inserted = 0
        if force:
            self._erase_history_regions(view)
            all_text = "\n".join([line.text for line in history] + texts)
            view.replace(edit, sublime.Region(0, view.size()), all_text)
            self.history_applied = len(history)
            self.last_texts = texts
            self._history_reset = False
            self._add_history_regions(view, 0, len(history))
        else:
            if self.history_visible and self.history_applied < len(self.history):
                old = self.history_applied
                new = self.history[old:]
                point = view.text_point(old, 0)
                view.insert(edit, point, "\n".join(line.text for line in new) + "\n")
                self._add_history_regions(view, old, len(self.history))
                inserted = len(new)
                self.history_applied = len(self.history)

            live_start = view.text_point(self.history_applied, 0)
            if len(texts) != len(self.last_texts):
                view.replace(edit, sublime.Region(live_start, view.size()), "\n".join(texts))
            else:
                for i, text in enumerate(texts):
                    if i < len(self.last_texts) and self.last_texts[i] == text:
                        continue
                    point = view.text_point(self.history_applied + i, 0)
                    line_region = view.line(point)
                    view.replace(edit, line_region, text)
            self.last_texts = texts
        self._apply_regions(view, frame, self.history_applied)
        return inserted

    def _apply_regions(self, view: sublime.View, frame: Frame, offset=0):
        if not view.is_valid():
            return
        for key in self.region_keys:
            view.erase_regions(key)
        for key in self.underline_keys:
            view.erase_regions(key)
        self.region_keys = []
        self.underline_keys = []

        grouped = {}
        under_grouped = {}
        for i, line in enumerate(frame.lines):
            if not line.text:
                continue
            row = offset + i
            for start, stop, pair in line.spans:
                if pair[0] == self.default_fg and pair[1] == self.default_bg:
                    continue
                scope = term_theme.scope(pair[0], pair[1])
                a = view.text_point(row, start)
                b = view.text_point(row, stop)
                if b > a:
                    grouped.setdefault(scope, []).append(sublime.Region(a, b))
            for start, stop, color in line.underlines:
                scope = term_theme.underline_scope(color)
                a = view.text_point(row, start)
                b = view.text_point(row, stop)
                if b > a:
                    under_grouped.setdefault(scope, []).append(sublime.Region(a, b))

        term_theme.apply(view)
        for index, (scope, regions) in enumerate(grouped.items()):
            key = "sublime_term_color_{}".format(index)
            view.add_regions(key, regions, scope)
            self.region_keys.append(key)
        flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE
        for index, (scope, regions) in enumerate(under_grouped.items()):
            key = "sublime_term_underline_{}".format(index)
            view.add_regions(key, regions, scope, flags=flags)
            self.underline_keys.append(key)
        if frame.cursor_line >= 0 and frame.cursor_line < len(frame.lines):
            span = frame.lines[frame.cursor_line].cursor_span
            if span:
                point = view.text_point(offset + frame.cursor_line, span[0])
                selections = view.sel()
                if len(selections) == 1 and not selections[0].empty() and view.size() > 40:
                    if selections[0].size() >= view.size() * 0.9:
                        selections.clear()
                        selections.add(sublime.Region(point, point))
                if len(selections) == 1 and selections[0].empty():
                    if selections[0].b != point:
                        selections.clear()
                        selections.add(sublime.Region(point, point))
