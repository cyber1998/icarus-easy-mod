#!/usr/bin/env bash
# Build the macOS app bundle (validation vehicle; same spec as Windows/Linux).
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
if [ ! -x "$PY" ]; then
  echo "Python venv not found at $PY. Create it with: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

"$PY" -m pip install --quiet pyinstaller

if [ ! -f packaging/icon.icns ]; then
  echo "Generating packaging/icon.icns ..."
  iconset="packaging/build/icon.iconset"
  rm -rf "$iconset"
  mkdir -p "$iconset"
  for size in 16 32 64 128 256 512; do
    sips -z "$size" "$size" packaging/icon.png --out "$iconset/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z "$double" "$double" packaging/icon.png --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$iconset" -o packaging/icon.icns
fi

"$PY" -m PyInstaller --noconfirm --clean --distpath packaging/dist --workpath packaging/build packaging/app.spec

BINARY="packaging/dist/IcarusServerModManager/IcarusServerModManager"
"$PY" packaging/smoke_test.py "$BINARY" --port 8611
"$BINARY" --self-check

VERSION="$("$PY" -c 'import icarus_manager; print(icarus_manager.__version__)')"
ARCH="$(uname -m)"
ARTIFACT="packaging/dist/IcarusServerModManager-${VERSION}-macos-${ARCH}.tar.gz"
tar -C packaging/dist -czf "$ARTIFACT" IcarusServerModManager
echo "Artifact: $ARTIFACT"
