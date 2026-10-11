#!/usr/bin/env bash
# Native Linux build (no Docker). Used by CI and by Linux users building locally.
# Artifact: packaging/dist/IcarusServerModManager-<ver>-linux-x64.tar.gz
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

BUNDLE_DIR="packaging/dist/IcarusServerModManager"
BINARY="$BUNDLE_DIR/IcarusServerModManager"
"$PY" packaging/smoke_test.py "$BINARY" --port 8612
"$BINARY" --self-check

cp packaging/linux/run.sh "$BUNDLE_DIR/run.sh"
chmod +x "$BUNDLE_DIR/run.sh"
cp packaging/linux/icarus-server-mod-manager.desktop "$BUNDLE_DIR/"

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' icarus_manager/__init__.py)"
ARTIFACT="packaging/dist/IcarusServerModManager-${VERSION}-linux-x64.tar.gz"
tar -C packaging/dist -czf "$ARTIFACT" IcarusServerModManager
echo "Artifact: $ARTIFACT"
