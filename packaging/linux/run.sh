#!/bin/sh
# Launcher for the portable Linux build. Double-click or run: ./run.sh
cd "$(dirname "$0")"
exec ./IcarusServerModManager "$@"
