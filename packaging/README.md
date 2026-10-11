# Packaging

Builds a self-contained app for each OS with PyInstaller (onedir): the user needs no
Python, and the app opens in their browser when launched.

## Layout

| Path | Purpose |
|---|---|
| `launcher.py` | Frozen entry point: sets Streamlit theme/config env vars, picks a free port, opens the browser, `--self-check` mode |
| `app.spec` | PyInstaller spec (bundles `app.py`, `icarus_manager`, streamlit/altair/repak + metadata) |
| `smoke_test.py` | Launches a built binary, waits for `/_stcore/health`, kills it (used by all build scripts) |
| `make_icon.py` | Regenerates `icon.png` / `icon.ico` |
| `version_info.txt` | Windows exe metadata (keep in sync with `icarus_manager/__init__.py`) |
| `linux/` | `run.sh` + `.desktop` template added to the Linux tarball |
| `windows/` | `build_windows.ps1` + Inno Setup `installer.iss` |

## Building

Artifacts land in `packaging/dist/`.

**Windows without a Windows machine:** push this project to GitHub and run the
`Build` workflow (Actions tab -> Build -> Run workflow). It builds Windows (installer +
portable zip), Linux and macOS on real machines in the cloud and uploads everything as
downloadable artifacts. Pushing a tag like `v0.3.0` also attaches the artifacts to a
GitHub release automatically.

**macOS** (validates the whole recipe; also a usable build):

```bash
./packaging/build_macos.sh
# -> packaging/dist/IcarusServerModManager-<ver>-macos-<arch>.tar.gz
```

**Linux** (needs Docker; builds inside Ubuntu 22.04 for a wide glibc baseline):

```bash
./packaging/build_linux.sh
# -> packaging/dist/IcarusServerModManager-<ver>-linux-x64.tar.gz
```

On Linux you can also build natively without Docker (this is what CI uses):

```bash
./packaging/build_linux_native.sh
```

**Windows** (run on a Windows machine; Python 3.10+ required):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
# -> packaging/dist/IcarusServerModManager-<ver>-windows-x64.zip
# -> packaging/dist/installer/IcarusServerModManagerSetup-<ver>.exe  (if Inno Setup is installed)
```

Install Inno Setup with `winget install -e --id JRSoftware.InnoSetup` (the script will
still produce the portable zip without it).

Each build script runs the smoke test and `--self-check` against the freshly built
binary, so a broken bundle fails the build instead of shipping.

## Version bumps

Update `__version__` in `icarus_manager/__init__.py` and the two version strings in
`packaging/version_info.txt`.

## Notes

- Builds are unsigned: expect SmartScreen warnings on Windows and Gatekeeper warnings
  on macOS. Code signing certificates fix this if you ever need it.
- Expect ~240 MB unpacked / ~95 MB compressed per platform (Streamlit + pandas +
  pyarrow dominate).
- PyInstaller cannot cross-compile; each OS must build its own binary (or use CI).
- The packaged app keeps all user data in `~/.icarus_server_mod_manager` (settings,
  size cache, base-data cache, Oodle runtime), so builds can live in read-only
  locations like `Program Files`.
