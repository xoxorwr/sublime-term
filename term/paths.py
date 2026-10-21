from __future__ import annotations

import os
import re
from typing import NamedTuple

_TOKEN_RE = re.compile(r"\S+")
_SUFFIX_RE = re.compile(r"^(?P<path>.+?)(?::(?P<line>\d+))(?::(?P<col>\d+))?$")
_LEFT = "([{<\"'"
_RIGHT = ".,;!?)]}>\"'"


class PathMatch(NamedTuple):
    start: int
    end: int
    path: str
    line: int | None
    column: int | None


def _trim(token):
    start = 0
    end = len(token)
    while start < end and token[start] in _LEFT:
        start += 1
    while end > start and token[end - 1] in _RIGHT:
        end -= 1
    while end > start and token[end - 1] == ":":
        end -= 1
    return start, end


def _resolve(path, cwds):
    path = os.path.expanduser(path)
    if os.path.isabs(path):
        candidates = [path]
    else:
        candidates = [os.path.join(cwd, path) for cwd in cwds if cwd]
    for candidate in candidates:
        candidate = os.path.normpath(candidate)
        if os.path.isfile(candidate):
            return candidate
    return None


def find_at(text, column, cwds):
    for match in _TOKEN_RE.finditer(text):
        if not (match.start() <= column <= match.end()):
            continue
        rel_start, rel_end = _trim(match.group())
        if rel_start >= rel_end:
            continue
        start = match.start() + rel_start
        end = match.start() + rel_end
        raw = text[start:end]
        line = None
        col = None
        suffix = _SUFFIX_RE.match(raw)
        if suffix:
            path = suffix.group("path")
            line = int(suffix.group("line"))
            if suffix.group("col"):
                col = int(suffix.group("col"))
        else:
            path = raw
        resolved = _resolve(path, cwds)
        if not resolved:
            continue
        return PathMatch(start, end, resolved, line, col)
    return None


def find_all(text, cwds):
    results = []
    for match in _TOKEN_RE.finditer(text):
        rel_start, rel_end = _trim(match.group())
        if rel_start >= rel_end:
            continue
        start = match.start() + rel_start
        end = match.start() + rel_end
        raw = text[start:end]
        line = None
        col = None
        suffix = _SUFFIX_RE.match(raw)
        if suffix:
            path = suffix.group("path")
            line = int(suffix.group("line"))
            if suffix.group("col"):
                col = int(suffix.group("col"))
        else:
            path = raw
        resolved = _resolve(path, cwds)
        if resolved:
            results.append(PathMatch(start, end, resolved, line, col))
    return results
