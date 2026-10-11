#!/usr/bin/env bash
# Native Linux build (no Docker). Used by CI and by Linux users building locally.
# Artifact: packaging/dist/IcarusEasyMod-<ver>-linux-x64.tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-}"
if [ -z "$PY" ]; then
  python3 -m venv .venv-build
  PY=".venv-build/bin/python"
fi

"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r requirements.txt pyinstaller

"$PY" -m PyInstaller --noconfirm --clean --distpath packaging/dist --workpath packaging/build packaging/app.spec

BUNDLE_DIR="packaging/dist/IcarusEasyMod"
BINARY="$BUNDLE_DIR/IcarusEasyMod"
"$PY" packaging/smoke_test.py "$BINARY" --port 8612
"$BINARY" --self-check

cp packaging/linux/run.sh "$BUNDLE_DIR/run.sh"
chmod +x "$BUNDLE_DIR/run.sh"
cp packaging/linux/icarus-easy-mod.desktop "$BUNDLE_DIR/"

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' icarus_manager/__init__.py)"
ARTIFACT="packaging/dist/IcarusEasyMod-${VERSION}-linux-x64.tar.gz"
tar -C packaging/dist -czf "$ARTIFACT" IcarusEasyMod
echo "Artifact: $ARTIFACT"
