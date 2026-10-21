# sublime_term

A real terminal emulator for Sublime Text on Linux and macOS, backed by
[libghostty-vt](https://github.com/ghostty-org/ghostty). It runs an interactive
PTY inside a normal Sublime Text view and renders the terminal with regions, so
the text remains selectable and searchable.

## Features

- Full VT emulation from Ghostty's `libghostty-vt`
- 16, 256 and 24-bit color (exact colors, including truecolor)
- Scrollback with mouse-wheel and keyboard navigation
- Native Sublime Text selection, copy and paste
- Bracketed paste
- OSC 52 clipboard writes (works with `tmux set-clipboard on`)
- Kitty keyboard protocol
- xterm mouse protocols, including SGR mouse and wheel forwarding
- tmux mouse mode
- Alternate screen, reflow on resize, cursor styles, window titles
- Focus in/out events
- Command invocation from the palette or the command line

Kitty graphics sequences are parsed by libghostty-vt, but Sublime Text has no
way to overlay raster images in a text view, so inline images are not drawn.

## Installation

Put this folder in Sublime Text's `Packages` directory (Preferences → Browse
Packages…). It must be a directory package, not a `.sublime-package`, because
the generated color scheme is written into the package.

The repository includes `lib/libghostty-vt.so` for x86_64 Linux. On another
architecture, or to rebuild against a newer Ghostty, run:

```sh
./scripts/build-libghostty.sh
```

This requires Zig 0.17.0 and clones Ghostty at the pinned commit.

## Usage

Open the command palette and run one of:

- `Terminal: New`
- `Terminal: New Here`
- `Terminal: Run Command…`
- `Terminal: New tmux Session…`
- `Terminal: Restart`
- `Terminal: Close`
- `Terminal: Copy`
- `Terminal: Paste`
- `Terminal: Clear Scrollback`
- `Terminal: Settings`

From the command line:

```sh
subl --command terminal_open
subl --command terminal_open_here
```

The default key bindings only apply while a terminal view has focus:

| Keys | Action |
| --- | --- |
| `Ctrl+Shift+C`, `Ctrl+Insert` | Copy selection |
| `Ctrl+Shift+V`, `Shift+Insert` | Paste |
| `Ctrl+C` | Send SIGINT |
| `Ctrl+Shift+P` | Sublime Text command palette |
| `Shift+PageUp` / `Shift+PageDown` | Scroll back / forward |
| `Ctrl+Shift+Up` / `Ctrl+Shift+Down` | Scroll one row |
| `Ctrl+Shift+Home` / `Ctrl+Shift+End` | Scroll to top / bottom |
| Mouse wheel | Scroll terminal (or forward to a mouse-aware app) |
| `Shift` + drag | Select text even when the app captures the mouse |

`Ctrl+Shift+C` and `Ctrl+Shift+V` can be remapped in your user keymap. On
macOS, `Cmd+C` and `Cmd+V` are also bound.

Selecting text uses Sublime's native selection. Copying trims trailing spaces
from each selected line.

## tmux

tmux works out of the box. For mouse support and clipboard passthrough, use:

```tmux
set -g mouse on
set -g set-clipboard on
set -s extended-keys on
set -as terminal-features 'xterm*:extkeys'
```

Mouse clicks, drags and wheel events are forwarded when tmux enables mouse
tracking. Wheel scrolling enters tmux copy mode. Shift+wheel always scrolls the
outer terminal instead. Using tmux's copy mode with `set-clipboard on` copies
through OSC 52 into Sublime Text's clipboard.

`Terminal: New tmux Session…` creates or attaches to a named session with:

```sh
tmux new-session -A -s <name>
```

## Settings

Settings live in `sublime_term.sublime-settings`:

```json
{
    "libghostty_path": "",
    "shell": "",
    "font_face": "monospace",
    "font_size": 12,
    "line_height": 1.0,
    "foreground": "#d8dee9",
    "background": "#1e1e1e",
    "cursor": "#d8dee9",
    "selection": "#3b4252",
    "selection_foreground": "#eceff4",
    "scrollback_lines": 10000,
    "scrollback_bytes": 33554432
}
```

`libghostty_path` may be absolute or relative to `Packages`. If empty, the
bundled library is tried first, followed by `/opt/ghostty/lib` and the system
library directories. `SUBLIME_TERM_LIBGHOSTTY` overrides all of them.

The terminal font must be monospaced. The view is configured to hide gutter,
line numbers, folding, wrapping, indent guides and whitespace markers.

## Architecture

- `term/ghostty.py` — ctypes binding for libghostty-vt: terminal, render state,
  key encoder, mouse encoder, clipboard and effect callbacks.
- `term/pty.py` — PTY process and non-blocking I/O.
- `term/session.py` — per-view terminal session, sizing, lifecycle and input.
- `term/render.py` — converts the libghostty screen into Sublime text and
  regions.
- `term/theme.py` — generates a hidden color scheme whose rules map each
  foreground/background color pair used on screen to a Sublime region scope.
- `term/commands.py`, `term/listeners.py`, `term/keys.py` — commands and input
  integration.

The screen is rendered as one line per terminal row. The whole viewport is
redrawn only when its content changes. Scrollback is handled by libghostty's
viewport; scrolling does not require keeping a second copy of the screen in
Python.

## License

MIT for this plugin. `libghostty-vt` and the bundled shared library are MIT
licensed; see `LICENSES/Ghostty-MIT.txt`.
