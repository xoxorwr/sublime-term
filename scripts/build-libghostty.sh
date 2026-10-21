#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT="${GHOSTTY_COMMIT:-67edd20a0292629da7e01b64973de19d356df487}"
SRC="${GHOSTTY_SRC:-$ROOT/.ghostty-src}"
OUT="${GHOSTTY_OUT:-$ROOT/.ghostty-build}"
ZIG="${ZIG:-zig}"

if ! command -v "$ZIG" >/dev/null 2>&1; then
    echo "zig is required (Ghostty currently needs Zig 0.17.0)" >&2
    exit 1
fi

if [ ! -d "$SRC/.git" ]; then
    git clone https://github.com/ghostty-org/ghostty.git "$SRC"
fi
git -C "$SRC" fetch --all --tags
git -C "$SRC" checkout "$COMMIT"

cd "$SRC"
"$ZIG" build -Demit-lib-vt=true -Doptimize=ReleaseFast -p "$OUT"

mkdir -p "$ROOT/lib"
cp "$OUT/lib/libghostty-vt.so.0.1.0" "$ROOT/lib/"
ln -sf libghostty-vt.so.0.1.0 "$ROOT/lib/libghostty-vt.so.0"
ln -sf libghostty-vt.so.0 "$ROOT/lib/libghostty-vt.so"
echo "Installed $ROOT/lib/libghostty-vt.so"
