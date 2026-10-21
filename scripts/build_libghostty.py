#!/usr/bin/env python3
"""Build libghostty-vt for the host OS and install it into the plugin."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMMIT = "67edd20a0292629da7e01b64973de19d356df487"
LIB_NAMES = {
    "Linux": "libghostty-vt.so",
    "Darwin": "libghostty-vt.dylib",
    "Windows": "ghostty-vt.dll",
}


def run(args, cwd=None):
    print("+", " ".join(str(a) for a in args))
    subprocess.run(args, cwd=cwd, check=True)


def find_zig():
    zig = os.environ.get("ZIG") or shutil.which("zig")
    if not zig:
        raise SystemExit("zig was not found. Ghostty requires Zig 0.17.0.")
    return zig


def find_library(out_dir: Path):
    names = []
    for folder in (out_dir / "lib", out_dir / "bin"):
        if not folder.is_dir():
            continue
        for entry in folder.iterdir():
            name = entry.name
            if not entry.is_file():
                continue
            if name.startswith("libghostty-vt") and name.endswith(".so"):
                names.append(entry)
            elif name.startswith("libghostty-vt") and ".so." in name:
                names.append(entry)
            elif name.startswith("libghostty-vt") and name.endswith(".dylib"):
                names.append(entry)
            elif name.startswith("ghostty-vt") and name.endswith(".dll"):
                names.append(entry)
    if not names:
        raise SystemExit("Could not find a built libghostty-vt shared library under " + str(out_dir))
    system = platform.system()
    if system == "Linux":
        preferred = [p for p in names if p.name == "libghostty-vt.so"]
    elif system == "Darwin":
        preferred = [p for p in names if p.name == "libghostty-vt.dylib"]
    elif system == "Windows":
        preferred = [p for p in names if p.name == "ghostty-vt.dll"]
    else:
        preferred = []
    return (preferred or sorted(names, key=lambda p: p.name))[0]


def install(src: Path):
    system = platform.system()
    name = LIB_NAMES.get(system)
    if not name:
        raise SystemExit("Unsupported host OS: " + system)
    lib_dir = ROOT / "lib"
    lib_dir.mkdir(exist_ok=True)
    patterns = {
        "Linux": ("libghostty-vt.so", "libghostty-vt.so.*"),
        "Darwin": ("libghostty-vt.dylib", "libghostty-vt.*.dylib"),
        "Windows": ("ghostty-vt.dll",),
    }[system]
    for pattern in patterns:
        for old in lib_dir.glob(pattern):
            if old.is_file() or old.is_symlink():
                old.unlink()
    dest = lib_dir / name
    shutil.copyfile(src, dest)
    if system != "Windows":
        dest.chmod(0o755)
    if system == "Linux":
        strip = shutil.which("strip")
        if strip:
            subprocess.run([strip, "--strip-debug", str(dest)], check=False)
    print("Installed", dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default=os.environ.get("GHOSTTY_SRC", str(ROOT / ".ghostty-src")))
    parser.add_argument("--out", default=os.environ.get("GHOSTTY_OUT", str(ROOT / ".ghostty-build")))
    parser.add_argument("--repo", default="https://github.com/ghostty-org/ghostty.git")
    parser.add_argument("--commit", default=os.environ.get("GHOSTTY_COMMIT", DEFAULT_COMMIT))
    parser.add_argument("--no-install", action="store_true", help="build without copying into lib/")
    args = parser.parse_args()

    zig = find_zig()
    src = Path(args.src).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    print("zig:", subprocess.check_output([zig, "version"], text=True).strip())

    if not (src / ".git").is_dir():
        src.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", args.repo, str(src)])
    run(["git", "fetch", "--all", "--tags"], cwd=src)
    run(["git", "checkout", "--force", args.commit], cwd=src)

    run(
        [
            zig,
            "build",
            "-Demit-lib-vt=true",
            "-Doptimize=ReleaseFast",
            "-p",
            str(out),
        ],
        cwd=src,
    )

    library = find_library(out)
    print("Built", library)
    if not args.no_install:
        install(library)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        raise SystemExit("build failed: {}".format(e))
