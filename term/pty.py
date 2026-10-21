from __future__ import annotations

import fcntl
import os
import pty
import queue
import select
import shlex
import signal
import struct
import termios
import threading


class PtyProcess:
    def __init__(self, shell: str, cwd: str, argv=None, env=None):
        self.shell = shell
        self.cwd = cwd
        self.argv = argv
        self.env = env or {}
        self.pid = -1
        self.fd = -1
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._out = bytearray()
        self._thread = None
        self.output = queue.Queue()
        self.alive = False
        self.cols = 80
        self.rows = 24

    def start(self, cols: int, rows: int):
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        pid, fd = pty.fork()
        if pid == 0:
            try:
                if self.cwd and os.path.isdir(self.cwd):
                    os.chdir(self.cwd)
                env = os.environ.copy()
                env.update(self.env)
                env["TERM"] = self.env.get("TERM", "xterm-256color")
                if self.argv:
                    os.execvpe(self.argv[0], self.argv, env)
                shell_argv = shlex.split(self.shell) if " " in self.shell else [self.shell]
                if not shell_argv:
                    shell_argv = ["/bin/sh"]
                if len(shell_argv) == 1:
                    shell_argv.append("-l")
                os.execvpe(shell_argv[0], shell_argv, env)
            except BaseException as e:
                try:
                    os.write(2, ("sublime_term: failed to start shell: {}\r\n".format(e)).encode())
                except OSError:
                    pass
            os._exit(127)
        self.pid = pid
        self.fd = fd
        self.alive = True
        os.set_blocking(fd, False)
        self.resize(cols, rows)
        self._thread = threading.Thread(target=self._reader, name="sublime_term_pty", daemon=True)
        self._thread.start()

    def resize(self, cols: int, rows: int):
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        if self.fd < 0:
            return
        try:
            fcntl.ioctl(
                self.fd,
                termios.TIOCSWINSZ,
                struct.pack("HHHH", self.rows, self.cols, 0, 0),
            )
        except OSError:
            pass

    def write(self, data: bytes):
        if not data or self.fd < 0 or not self.alive:
            return
        with self._lock:
            self._out.extend(data)

    def _flush(self):
        with self._lock:
            data = bytes(self._out)
        if not data:
            return
        try:
            written = os.write(self.fd, data)
        except BlockingIOError:
            return
        except OSError:
            self.alive = False
            return
        if written:
            with self._lock:
                del self._out[:written]

    def _reader(self):
        try:
            while not self._stop.is_set():
                with self._lock:
                    want_write = bool(self._out)
                try:
                    readable, writable, _ = select.select(
                        [self.fd],
                        [self.fd] if want_write else [],
                        [],
                        0.1,
                    )
                except (OSError, ValueError):
                    break
                if writable:
                    self._flush()
                if not readable:
                    continue
                try:
                    data = os.read(self.fd, 65536)
                except BlockingIOError:
                    continue
                except OSError:
                    break
                if not data:
                    break
                self.output.put(data)
        finally:
            self.alive = False
            try:
                self.output.put(None)
            except Exception:
                pass
            self._reap()

    def _reap(self):
        if self.pid > 0:
            try:
                os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                pass

    def close(self):
        self._stop.set()
        self.alive = False
        if self.pid > 0:
            for sig in (signal.SIGHUP, signal.SIGTERM):
                try:
                    os.killpg(self.pid, sig)
                except OSError:
                    break
        if self.fd >= 0:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = -1
        self._reap()
