from __future__ import annotations

import os
import re
import time
from typing import NamedTuple

_TOKEN_RE = re.compile(r"\S+")
_SUFFIX_RE = re.compile(r"^(?P<path>.+?)(?::(?P<line>\d+))(?::(?P<col>\d+))?$")
_LEFT = "([{<\"'"
_RIGHT = ".,;!?)]}>\"'"
_ROOT_CACHE = {}
_ROOT_CACHE_TTL = 10.0


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


def _find_in_roots(name, roots):
    now = time.monotonic()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        root = os.path.abspath(root)
        key = (root, name)
        cached = _ROOT_CACHE.get(key)
        if cached and now - cached[0] < _ROOT_CACHE_TTL:
            if cached[1] is None or os.path.isfile(cached[1]):
                return cached[1]
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in (".git", ".hg", ".svn")]
            if name in files:
                candidate = os.path.join(dirpath, name)
                if os.path.isfile(candidate):
                    _ROOT_CACHE[key] = (now, candidate)
                    return candidate
        _ROOT_CACHE[key] = (now, None)
    return None


def _resolve(path, cwds, roots=None):
    path = os.path.expanduser(path)
    roots = roots or []
    if os.path.isabs(path):
        candidates = [path]
    else:
        candidates = [os.path.join(cwd, path) for cwd in cwds if cwd]
        candidates.extend(os.path.join(root, path) for root in roots if root)
    for candidate in candidates:
        candidate = os.path.normpath(candidate)
        if os.path.isfile(candidate):
            return candidate
    if os.path.isabs(path):
        return None
    return _find_in_roots(os.path.basename(path), roots)


def find_at(text, column, cwds, roots=None):
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
        resolved = _resolve(path, cwds, roots)
        if not resolved:
            continue
        return PathMatch(start, end, resolved, line, col)
    return None


def find_all(text, cwds, roots=None):
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
        resolved = _resolve(path, cwds, roots)
        if resolved:
            results.append(PathMatch(start, end, resolved, line, col))
    return results
