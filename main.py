import sys

prefix = __package__ + "."
for module_name in [
    module_name
    for module_name in sys.modules
    if module_name.startswith(prefix) and module_name != __name__
]:
    del sys.modules[module_name]
del prefix

from .term import ghostty, manager  # noqa: E402
from .term.commands import *  # noqa: E402,F401,F403
from .term.listeners import *  # noqa: E402,F401,F403


def plugin_loaded():
    if not ghostty.available():
        print("sublime_term: libghostty-vt not available")


def plugin_unloaded():
    manager.close_all()
