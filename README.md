# Icarus Server Mod Manager

A friendly Streamlit app for managing mods on an Icarus dedicated server. Look up mods
from the community database, download them, and push them to your server over FTP, FTPS,
or SFTP with one click. No separate FTP client needed.

## Install & run

Prebuilt versions bundle everything (no Python install required):

| OS | File | How to run |
|---|---|---|
| Windows | `IcarusServerModManagerSetup-<version>.exe` | Run the installer; it creates Start Menu and optional desktop shortcuts |
| Linux | `IcarusServerModManager-<version>-linux-x64.tar.gz` | Extract, then run `./run.sh` |
| macOS | `IcarusServerModManager-<version>-macos-<arch>.tar.gz` | Extract, then run the `IcarusServerModManager` binary |

The app opens in your browser automatically. Keep the console window open while you use
it - closing that window stops the app.

Notes:

- Windows SmartScreen may warn about an unknown publisher (builds are not code-signed).
  Choose "More info" then "Run anyway".
- The first time the app reads an Oodle-compressed game pak (for EXMODZ conversion), it
  downloads the Oodle runtime once. If Icarus is installed on the same computer, the
  copy inside the game install is used instead.
- Building your own binaries: see `packaging/README.md`.

## Features

- Connect with FTP, FTPS (explicit TLS), or SFTP using the details from your game server host.
- Automatically finds the server's mods folder (`Icarus/Content/Paks/mods`), even on hosts
  that nest it inside a config number folder.
- Browse and search the ProjectDaedalus community index (500+ mods) and install one or
  many mods at once. The list shows name, size, week and type; click a mod's name for
  full details and the link icon to open its page.
- Optionally copy every uploaded mod into your own Icarus game folder as well
  (auto-detects the usual Steam locations), so you can play with the same mods.
- Upload your own `.pak` files or `.zip` archives from your computer.
- Converts `.EXMODZ`/`.EXMOD` data mods automatically: their row changes are merged
  with the data from your local Icarus install and packed into a loadable `_P.pak`.
- Inspect `.pak` files before uploading (the app lists what is inside them).
- View what is currently installed on the server, spot different versions, and delete mods.

## Run from source

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens in your browser at http://localhost:8501.

Reading the game's paks (for EXMODZ conversion) uses the
[repak](https://pypi.org/project/repak/) library; if a pak is Oodle-compressed,
repak resolves the Oodle runtime automatically on first use (or honors
`REPAK_OODLE_PATH` to point at a copy you already have, such as the one shipped
inside your Icarus install).

## Usage

1. **Browse Mods** - Search or filter by author. No server connection is needed to
   browse. Click a mod's name for full details (author, description, install status),
   use the link icon for its ProjectDaedalus page, and tick the checkboxes to select
   mods. When you are ready, connect on the Connect page and press
   *Add selected mods to server*.
2. **Connect** - Enter the FTP/SFTP details from your host's control panel (GPortal,
   Nitrado, BisectHosting, Survival Servers, etc.). Leave the mods folder blank to
   auto-detect it, or paste the full path, for example `/Icarus/Content/Paks/mods`.
3. **Upload Local Files** - Already have a `.pak` or a `.zip` from NexusMods or a mod
   author? Add it here.
4. Restart your server from the host panel so it loads the new mods.

Set the optional **local game folder** on the Connect page (auto-detected on most Steam
installs) and the app will copy every uploaded mod into your own game too. The sidebar
toggle *Also install mods to my local game* controls this.

Every player who joins must install the same mods locally in their own game folder
(`steamapps/common/Icarus/Icarus/Content/Paks/mods`).

## Supported files

| File | Supported | Notes |
|---|---|---|
| `.pak` | Yes | The standard mod format |
| `.zip` | Yes | All `.pak` files inside are extracted and uploaded |
| `.ucas` / `.utoc` | Yes | Uploaded next to the `.pak` they belong to |
| `.EXMODZ` / `.EXMOD` | Yes | Converted automatically (see below) |
| `.rar` | No | Extract with 7-Zip/WinRAR and upload the `.pak` |

## How EXMODZ conversion works

`EXMODZ` packages (the format used by Icarus Mod Manager) contain row-level edits to
the game's JSON data tables, for example "change Wood's stack size to 200". Icarus can
only load `.pak` files, so the app:

1. reads the current base tables directly from your local Icarus install
   (using the [repak](https://pypi.org/project/repak/) library, which handles the
   game's compressed paks),
2. merges each mod's changes on top (multiple mods are merged in order; later mods win
   conflicts, matching Icarus Mod Manager), and
3. packs the result into a `_P.pak`, uploads it to the server, and copies it into your
   local game like any other mod.

Requirements: Icarus installed on this computer (set the local game folder on the
Connect page) and the same weekly update on the local game and the server. Files that
do not exist in your game version are skipped and reported in the install log.

## Tests

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests
```

Includes unit tests for archive handling, a mock FTP server integration test, and a
smoke test of the Streamlit UI. The catalog test hits projectdaedalus.app live and
skips itself when there is no network access.

## Troubleshooting

| Problem | Fix |
|---|---|
| Login failed | Double-check the username/password in your host's panel; some hosts show separate FTP and SFTP accounts |
| Timed out connecting | Verify host and port; try SFTP (port 22) if the host does not offer FTP |
| "Server does not accept the selected protocol" | Try plain FTP instead of FTPS, or SFTP |
| Mods folder not found | Open the host's file manager, find `Icarus/Content/Paks`, and enter its full path (ending in `mods`) on the Connect page |
| Mods not copied to my game | Set your local game folder on the Connect page and make sure the sidebar toggle is on |
| EXMODZ conversion fails | Make sure the local game folder is set on the Connect page and Icarus is fully installed and updated; the game and server must be on the same week |
| "Oodle runtime could not be loaded" | repak normally downloads it automatically; alternatively set `REPAK_OODLE_PATH` to the `oo2core_*` DLL inside your Icarus install |
| Mods not loading in game | Restart the server; make sure players have the identical mods installed locally |
| Catalog shows HTTP 403 | The mod index temporarily rate-limited the app; wait a minute and search again |

## Notes

- Connection settings (host, port, username, folder) are optionally remembered in
  `~/.icarus_server_mod_manager/config.json`. Passwords are never saved.
- SFTP connections trust the server's host key on first connect, like most simple SFTP clients.
- Mod listings come from the community database at
  [projectdaedalus.app](https://www.projectdaedalus.app); downloads come from each mod's
  original release link (usually GitHub).

## License

MIT - see [LICENSE](LICENSE). Third-party components and their license texts are listed
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Acknowledgements

- [ProjectDaedalus](https://www.projectdaedalus.app) - the community mod index this app browses
- [Icarus Mod Manager](https://github.com/Jimk72/Icarus_Software) by Jimk72 - the
  EXMOD/EXMODZ format and merge workflow this app reimplements
- [NetPak](https://github.com/CrystalFerrai/NetPak) by Crystal Ferrai (Apache-2.0) -
  reference implementation for the `.pak` format handling
- [repak](https://github.com/trumank/repak) - pak reading and Oodle loading
