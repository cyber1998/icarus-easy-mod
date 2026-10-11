#!/usr/bin/env bash
# Build the Linux tarball inside an Ubuntu 22.04 container (wide glibc baseline).
# Requires Docker. Artifact: packaging/dist/IcarusEasyMod-<ver>-linux-x64.tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."

docker run --rm -v "$PWD:/src" -w /src ubuntu:22.04 bash -lc '
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip ca-certificates >/dev/null
python3 -m venv /tmp/buildenv
/tmp/buildenv/bin/pip install --quiet --upgrade pip
/tmp/buildenv/bin/pip install --quiet -r requirements.txt pyinstaller
/tmp/buildenv/bin/python -m PyInstaller --noconfirm --clean --distpath packaging/dist --workpath packaging/build packaging/app.spec
/tmp/buildenv/bin/python packaging/smoke_test.py packaging/dist/IcarusEasyMod/IcarusEasyMod --port 8612
packaging/dist/IcarusEasyMod/IcarusEasyMod --self-check
'

cp packaging/linux/run.sh packaging/dist/IcarusEasyMod/run.sh
chmod +x packaging/dist/IcarusEasyMod/run.sh
cp packaging/linux/icarus-easy-mod.desktop packaging/dist/IcarusEasyMod/

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' icarus_manager/__init__.py)"
ARTIFACT="packaging/dist/IcarusEasyMod-${VERSION}-linux-x64.tar.gz"
tar -C packaging/dist -czf "$ARTIFACT" IcarusEasyMod
echo "Artifact: $ARTIFACT"
