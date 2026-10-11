"""Streamlit UI for the Icarus Server Mod Manager."""

from __future__ import annotations

import html
import json
import math
import posixpath
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlsplit

import requests
import streamlit as st

from icarus_manager import __version__, archives, catalog, converter, exmod, localgame, settings
from icarus_manager.remote import (
    FtpServer,
    RemoteError,
    RemoteFile,
    SftpServer,
    ensure_mods_dir,
    find_icarus_root,
    list_mod_files,
)
from icarus_manager.util import base_mod_key, human_size
from icarus_manager.uepak import PakError, PakFile

PAGES = ["Connect", "Browse Mods", "Upload Local Files", "Installed Mods", "Help"]
PROTOCOLS = ["FTP", "FTPS", "SFTP"]
DEFAULT_PORTS = {"FTP": 21, "FTPS": 21, "SFTP": 22}
PAGE_SIZE = 25
SIZE_CACHE_FILE = settings.CONFIG_DIR / "size_cache.json"

st.set_page_config(page_title="Icarus Server Mod Manager", layout="wide")

_THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Rubik:wght@400;500;600&display=swap');

:root {
  --icarus-gold: #f2b544;
  --icarus-gold-soft: #ffd479;
  --icarus-gold-deep: #e08a1e;
  --line: rgba(255, 255, 255, 0.10);
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
  font-family: 'Rubik', system-ui, -apple-system, 'Segoe UI', sans-serif;
}

[data-testid="stAppViewContainer"] {
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.022) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.022) 1px, transparent 1px),
    radial-gradient(1100px 520px at 85% -10%, rgba(242, 181, 68, 0.10), transparent 60%),
    radial-gradient(900px 480px at -10% 110%, rgba(64, 140, 255, 0.07), transparent 55%);
  background-size: 46px 46px, 46px 46px, auto, auto;
  background-color: #0d1117;
  background-attachment: fixed;
}

[data-testid="stHeader"] { background: transparent; }

h1, h2, h3, h4 { font-family: 'Chakra Petch', 'Rubik', sans-serif !important; letter-spacing: .02em; }

[data-testid="stMarkdownContainer"] h2 { position: relative; padding-left: .8rem; }
[data-testid="stMarkdownContainer"] h2::before {
  content: ""; position: absolute; left: 0; top: .14em; bottom: .2em; width: 4px; border-radius: 3px;
  background: linear-gradient(180deg, var(--icarus-gold-soft), var(--icarus-gold-deep));
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #131822 0%, #0b0e13 100%);
  border-right: 1px solid rgba(242, 181, 68, .14);
}
[data-testid="stSidebar"] h1 {
  background: linear-gradient(92deg, #ffd479 10%, #ff9b2f 90%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  font-weight: 700;
}
[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] { gap: .15rem; }
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  padding: .38rem .55rem; border-radius: 9px; transition: background .15s ease;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background: rgba(242, 181, 68, .08); }

[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #ffd479, #e08a1e 85%);
  color: #16100a !important; font-weight: 700; border: none; border-radius: 10px;
  box-shadow: 0 1px 0 rgba(255, 255, 255, .25) inset, 0 8px 22px rgba(224, 138, 30, .28);
}
[data-testid="stBaseButton-primary"]:hover {
  filter: brightness(1.06);
  box-shadow: 0 10px 26px rgba(224, 138, 30, .4);
}
[data-testid="stBaseButton-primary"]:active { transform: translateY(1px); }
[data-testid="stBaseButton-primary"] p { color: #16100a !important; }
[data-testid="stBaseButton-primary"]:disabled {
  background: linear-gradient(135deg, rgba(255, 212, 121, .30), rgba(224, 138, 30, .30)) !important;
  color: rgba(22, 16, 10, .70) !important;
  box-shadow: none !important; opacity: .75;
}
[data-testid="stBaseButton-primary"]:disabled p { color: rgba(22, 16, 10, .70) !important; }

[data-testid="stBaseButton-secondary"] {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--line); border-radius: 10px; color: #e8e6e1;
}
[data-testid="stBaseButton-secondary"]:hover {
  border-color: rgba(242, 181, 68, .5); color: var(--icarus-gold-soft);
  background: rgba(242, 181, 68, .07);
}

[data-testid="stBaseButton-tertiary"] {
  justify-content: flex-start !important; text-align: left !important;
  padding: .12rem .35rem; border-radius: 8px;
  color: #f2f4f7; font-weight: 600;
}
[data-testid="stBaseButton-tertiary"] div, [data-testid="stBaseButton-tertiary"] p {
  text-align: left !important; justify-content: flex-start !important;
}
[data-testid="stBaseButton-tertiary"]:hover {
  background: rgba(242, 181, 68, .09); color: var(--icarus-gold-soft);
}
[data-testid="stBaseButton-tertiary"] p { font-family: 'Chakra Petch', 'Rubik', sans-serif; }

[data-testid="stLinkButton"] a {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--line); border-radius: 9px;
  color: #cfd6e0 !important;
  display: flex; justify-content: center; align-items: center;
}
[data-testid="stLinkButton"] a:hover {
  border-color: rgba(242, 181, 68, .55); color: var(--icarus-gold-soft) !important;
  background: rgba(242, 181, 68, .08);
}

[data-testid="stDialog"] > div {
  border: 1px solid rgba(242, 181, 68, .22);
  border-radius: 14px;
  background: linear-gradient(180deg, #161b24, #10141a);
  box-shadow: 0 24px 80px rgba(0, 0, 0, .65);
}

[data-testid="stAlertContainer"] { border-radius: 10px; border: 1px solid rgba(255, 255, 255, .09); }

[data-testid="stCaptionContainer"] p { color: #99a2af; }

.chip {
  display: inline-block; padding: 1px 10px; border-radius: 999px;
  font-size: .73rem; font-weight: 600; letter-spacing: .05em; text-transform: uppercase;
}
.chip-pak { background: rgba(84, 214, 138, .14); color: #7fe0a1; border: 1px solid rgba(84, 214, 138, .35); }
.chip-exmodz { background: rgba(242, 181, 68, .14); color: #ffd479; border: 1px solid rgba(242, 181, 68, .42); }
.chip-zip { background: rgba(110, 160, 255, .14); color: #a5c4ff; border: 1px solid rgba(110, 160, 255, .35); }
.chip-other { background: rgba(255, 255, 255, .07); color: #cfd6e0; border: 1px solid rgba(255, 255, 255, .15); }
.chip-week {
  background: rgba(255, 255, 255, .05); color: #cfd6e0; border: 1px solid rgba(255, 255, 255, .12);
  text-transform: none; letter-spacing: .02em;
}
.th {
  font-size: .72rem; letter-spacing: .14em; text-transform: uppercase;
  color: #8b93a0; font-weight: 600;
}
.dim { color: #aeb6c2; }
"""


def _inject_theme() -> None:
    st.markdown(f"<style>{_THEME_CSS}</style>", unsafe_allow_html=True)


def _type_chip(download_type: str) -> str:
    value = (download_type or "").strip()
    if not value:
        return "-"
    lowered = value.lower()
    if lowered.startswith("exmod"):
        css_class = "chip-exmodz"
    elif lowered.startswith("zip"):
        css_class = "chip-zip"
    elif lowered.startswith("pak"):
        css_class = "chip-pak"
    else:
        css_class = "chip-other"
    return f'<span class="chip {css_class}">{html.escape(value)}</span>'


def _week_chip(week: str) -> str:
    value = (week or "").strip()
    if not value:
        return "-"
    return f'<span class="chip chip-week">{html.escape(value)}</span>'


def make_server(creds: dict):
    protocol = str(creds.get("protocol", "FTP")).upper()
    if protocol == "SFTP":
        return SftpServer(
            host=creds["host"],
            port=creds.get("port"),
            username=creds.get("username", ""),
            password=creds.get("password", ""),
        )
    return FtpServer(
        host=creds["host"],
        port=creds.get("port"),
        username=creds.get("username", ""),
        password=creds.get("password", ""),
        tls=(protocol == "FTPS"),
    )


def require_connection():
    if not st.session_state.get("connected"):
        st.info("Not connected yet. Open the **Connect** page and sign in to your server first.")
        return None
    return st.session_state["creds"], st.session_state["mods_path"]


class _ProgressThrottle:
    def __init__(self, bar, label: str) -> None:
        self._bar = bar
        self._label = label
        self._last = 0.0

    def __call__(self, done: int, total: int) -> None:
        now = time.time()
        pct = (done / total) if total else 0.0
        if now - self._last < 0.15 and pct < 1.0:
            return
        self._last = now
        if total:
            text = f"{self._label} ({human_size(done)} / {human_size(total)})"
        else:
            text = f"{self._label} ({human_size(done)})"
        self._bar.progress(min(max(pct, 0.0), 1.0), text=text)


def _download_file(url: str, dest: Path) -> None:
    headers = {"User-Agent": catalog.USER_AGENT}
    try:
        with requests.get(url, headers=headers, stream=True, timeout=(20, 300), allow_redirects=True) as response:
            response.raise_for_status()
            with open(dest, "wb") as handle:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        handle.write(chunk)
    except requests.RequestException as exc:
        raise RuntimeError(str(exc)) from exc


def _pak_contents(path: Path) -> str:
    if path.suffix.lower() != ".pak":
        return ""
    try:
        return f"{len(PakFile(path).entries)} files"
    except (PakError, OSError):
        return ""


def _try_load_exmod(path: Path):
    try:
        return exmod.load_exmod(path)
    except (exmod.ExModError, OSError):
        return None


def _convert_data_mods(
    data_mods: list, workdir: Path, log
) -> tuple[list[tuple[Path, str]], list[str]]:
    local_path = st.session_state.get("local_mods_path")
    if not local_path:
        names = ", ".join(mod.name for mod in data_mods)
        return [], [
            f"EXMOD data mods ({names}) must be converted into a .pak, which requires "
            "your local Icarus game folder. Set it on the Connect page."
        ]
    try:
        result = converter.convert_mods(data_mods, Path(local_path), workdir)
    except converter.ConversionError as exc:
        return [], [f"EXMOD conversion failed: {exc}"]
    report = result.report
    log(f"Converted {len(data_mods)} EXMOD mod(s) into {result.pak_path.name}")
    log(f"  merged {report.total_changed} row change(s), added {report.total_added} new row(s)")
    for note in report.conflicts:
        log(f"  note: {note}")
    for missing in report.missing:
        log(f"  skipped '{missing}' (not found in your game version)")
    log("  note: your local game must match the server's game week")
    return [(result.pak_path, result.pak_path.name)], []


def _basename_from_url(url: str) -> str:
    name = unquote(posixpath.basename(urlsplit(url).path))
    return name or "mod.pak"


def _upload_paks(
    creds: dict, mods_path: str, items: list[tuple[Path, str]], progress
) -> tuple[list[tuple[Path, str]], list[str], Optional[str]]:
    uploaded: list[tuple[Path, str]] = []
    failures: list[str] = []
    connection_error: Optional[str] = None
    try:
        with make_server(creds) as server:
            for local_path, remote_name in items:
                progress.progress(0.0, text=f"Uploading {remote_name}...")
                try:
                    server.upload_file(
                        str(local_path),
                        posixpath.join(mods_path, remote_name),
                        _ProgressThrottle(progress, f"Uploading {remote_name}"),
                    )
                    uploaded.append((local_path, remote_name))
                except RemoteError as exc:
                    failures.append(f"{remote_name}: {exc}")
    except RemoteError as exc:
        connection_error = str(exc)
    return uploaded, failures, connection_error


def _copy_local(uploaded_items: list[tuple[Path, str]]) -> None:
    if not uploaded_items or not st.session_state.get("copy_to_local"):
        return
    local_path = st.session_state.get("local_mods_path")
    if not local_path:
        st.info(
            "Tip: set your local game folder on the Connect page to also install these mods "
            "into your own Icarus game automatically."
        )
        return
    copied, failures = localgame.copy_paks([local for local, _ in uploaded_items], Path(local_path))
    if copied:
        st.success(f"Also copied {len(copied)} file(s) into your local game folder.")
    for failure in failures:
        st.warning(f"Local copy failed: {failure}")


def _mark_mods_changed() -> None:
    st.session_state["pending_restart"] = True
    st.session_state["server_files"] = None
    st.session_state["server_files_at"] = 0.0


def _pending_restart_banner() -> None:
    if not st.session_state.get("pending_restart"):
        return
    left, right = st.columns([6, 1])
    with left:
        st.warning(
            "Mod files were changed. Restart your Icarus server to apply them, and make sure "
            "every player installs the same mods locally."
        )
    with right:
        if st.button("Dismiss", use_container_width=True):
            st.session_state["pending_restart"] = False
            st.rerun()


@st.cache_data(ttl=600, show_spinner=False)
def load_catalog(query: str, download_type: str, author: str, page: int) -> catalog.CatalogResult:
    return catalog.fetch_catalog(query=query, download_type=download_type, author=author, page=page)


@st.cache_data(ttl=3600, show_spinner=False)
def load_authors() -> list[tuple[str, str]]:
    try:
        return catalog.fetch_catalog(download_type="pak").authors
    except catalog.CatalogError:
        return []


def _server_files(creds: dict, mods_path: str, force: bool = False) -> list[RemoteFile]:
    now = time.time()
    cached = st.session_state.get("server_files")
    if force or cached is None or now - st.session_state.get("server_files_at", 0.0) > 120:
        try:
            with make_server(creds) as server:
                cached = list_mod_files(server, mods_path)
        except RemoteError as exc:
            st.warning(f"Could not list the server's mods folder: {exc}")
            cached = st.session_state.get("server_files") or []
        st.session_state["server_files"] = cached
        st.session_state["server_files_at"] = now
    return cached


def page_connect() -> None:
    st.header("Connect to your server")
    st.markdown(
        "Enter the FTP/SFTP details from your game server host's control panel. "
        "Leave the mods folder blank to let the app find it automatically."
    )

    profile = st.session_state["profile"]
    creds = st.session_state.get("creds") or {}
    default_protocol = creds.get("protocol") or profile.get("protocol") or "FTP"
    if default_protocol not in PROTOCOLS:
        default_protocol = "FTP"

    with st.form("connect_form"):
        col1, col2 = st.columns(2)
        with col1:
            protocol = st.selectbox("Protocol", PROTOCOLS, index=PROTOCOLS.index(default_protocol))
            host = st.text_input("Host", value=creds.get("host") or profile.get("host", ""), placeholder="ftp.example.com")
            port = st.text_input(
                "Port",
                value=str(creds.get("port") or profile.get("port") or ""),
                placeholder=str(DEFAULT_PORTS[default_protocol]),
            )
        with col2:
            username = st.text_input("Username", value=creds.get("username") or profile.get("username", ""))
            password = st.text_input("Password", type="password")
            remote_path = st.text_input(
                "Mods folder path (optional)",
                value=creds.get("remote_path") or profile.get("remote_path", ""),
                placeholder="/Icarus/Content/Paks/mods",
                help="Leave blank to auto-detect. This is the folder where .pak mods are uploaded.",
            )
        remember = st.checkbox("Remember these settings on this computer (password is never saved)", value=True)
        submitted = st.form_submit_button("Connect", type="primary")

    if submitted:
        errors: list[str] = []
        host = host.strip()
        username = username.strip()
        if not host:
            errors.append("Host is required.")
        if not username:
            errors.append("Username is required.")
        if not password:
            errors.append("Password is required.")
        try:
            port_number = int(port or DEFAULT_PORTS[protocol])
        except ValueError:
            errors.append("Port must be a number.")
            port_number = None
        if errors:
            st.error(" ".join(errors))
        else:
            candidate = {
                "protocol": protocol,
                "host": host,
                "port": port_number,
                "username": username,
                "password": password,
                "remote_path": remote_path.strip(),
            }
            try:
                with st.spinner(f"Connecting to {host}..."):
                    with make_server(candidate) as server:
                        if candidate["remote_path"]:
                            mods_path = candidate["remote_path"]
                            server.mkdirs(mods_path)
                        else:
                            root = find_icarus_root(server)
                            mods_path = ensure_mods_dir(server, root)
                        count = len(list_mod_files(server, mods_path))
            except RemoteError as exc:
                st.error(f"Connection failed: {exc}")
            else:
                st.session_state.update(
                    connected=True,
                    creds=candidate,
                    mods_path=mods_path,
                    server_label=f"{protocol} {host}:{port_number}",
                    server_files=None,
                    server_files_at=0.0,
                )
                if remember:
                    settings.save_profile(candidate)
                st.success(f"Connected. Mods folder: `{mods_path}` ({count} files currently installed).")

    if st.session_state.get("connected"):
        st.divider()
        st.success(f"Connected to {st.session_state['server_label']}")
        st.code(st.session_state["mods_path"], language=None)
        if st.button("Disconnect"):
            for key in ("connected", "creds", "mods_path", "server_label", "server_files", "server_files_at"):
                st.session_state.pop(key, None)
            st.rerun()

    st.divider()
    st.subheader("Local game copy (optional)")
    st.caption(
        "When set, every mod that is uploaded to the server is also copied into your own "
        "Icarus game folder, so you can join your server with the same mods."
    )
    detected = st.session_state.get("detected_local_path")
    if detected is None:
        detected = str(localgame.detect_local_mods_path() or "")
        st.session_state["detected_local_path"] = detected
    if "local_path_input" not in st.session_state:
        st.session_state["local_path_input"] = st.session_state.get("local_mods_path") or detected
    local_input = st.text_input(
        "Your local mods folder",
        key="local_path_input",
        placeholder="/steamapps/common/Icarus/Icarus/Content/Paks/mods",
        help="Point at the game's .../Icarus/Content/Paks/mods folder, or just its Paks folder.",
    )
    local_col1, local_col2 = st.columns([1, 1])
    if local_col1.button("Save local folder"):
        normalized = localgame.normalize_local_path(local_input)
        if normalized is None:
            st.error(
                "That path does not look like an Icarus folder. Point it at "
                ".../Icarus/Content/Paks/mods, .../Content/Paks, or the game folder itself."
            )
        else:
            try:
                localgame.ensure_mods_dir(normalized)
            except localgame.LocalGameError as exc:
                st.error(str(exc))
            else:
                st.session_state["local_mods_path"] = str(normalized)
                settings.save_profile({"local_mods_path": str(normalized)})
                st.success(f"Local game folder saved: `{normalized}`")
    if local_col2.button("Auto-detect"):
        st.session_state["local_path_input"] = detected
        st.rerun()
    if st.session_state.get("local_mods_path"):
        st.caption(f"Current: `{st.session_state['local_mods_path']}`")


def _mod_key(mod: catalog.ModEntry) -> str:
    return mod.filename or f"{mod.name}|{mod.author}"


def _size_cache() -> dict:
    cache = st.session_state.get("size_cache")
    if cache is None:
        cache = {}
        try:
            data = json.loads(SIZE_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cache = data
        except (OSError, ValueError):
            cache = {}
        st.session_state["size_cache"] = cache
    return cache


def _save_size_cache() -> None:
    cache = st.session_state.get("size_cache") or {}
    try:
        if len(cache) > 3000:
            newest = sorted(cache.items(), key=lambda item: item[1].get("at", 0), reverse=True)[:3000]
            cache = dict(newest)
            st.session_state["size_cache"] = cache
        settings.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SIZE_CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        pass


def _size_label(mod: catalog.ModEntry) -> str:
    if not mod.download_url:
        return ""
    entry = _size_cache().get(mod.download_url)
    if isinstance(entry, dict) and entry.get("size"):
        return human_size(entry["size"])
    return "?"


def _load_sizes(mods: list[catalog.ModEntry], progress) -> int:
    cache = _size_cache()
    pending: list[str] = []
    seen: set[str] = set()
    for mod in mods:
        url = mod.download_url
        if not url or url in cache or url in seen:
            continue
        seen.add(url)
        pending.append(url)
    if not pending:
        return 0
    loaded = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(catalog.fetch_size, url): url for url in pending}
        for index, future in enumerate(as_completed(futures), start=1):
            url = futures[future]
            try:
                size = future.result()
            except Exception:
                size = None
            if size:
                cache[url] = {"size": size, "at": time.time()}
                loaded += 1
            progress.progress(index / len(pending), text=f"Loaded {index}/{len(pending)} file sizes...")
    _save_size_cache()
    return loaded


@st.dialog("Mod details", width="large")
def _mod_dialog(mod: catalog.ModEntry, status: str, can_install: bool) -> None:
    st.subheader(mod.name)
    st.markdown(f"{_type_chip(mod.download_type)} {_week_chip(mod.week)}", unsafe_allow_html=True)
    left, right = st.columns(2)
    left.markdown(f"**Author:** {mod.author or 'unknown'}")
    left.markdown(f"**Version:** {mod.version or '-'}")
    left.markdown(f"**Week:** {mod.week or '-'}")
    right.markdown(f"**Download:** {mod.download_type or '-'}")
    right.markdown(f"**Updated:** {mod.updated or '-'}")
    right.markdown(f"**File:** {mod.filename or '-'}")
    size_text = _size_label(mod)
    st.markdown(f"**Size:** {human_size_label(size_text)}")
    if mod.download_type.upper().startswith("EXMOD"):
        st.caption("EXMOD data mod - converted automatically into a .pak when installed.")
    if can_install:
        st.markdown(f"**Server status:** {status or 'Not installed'}")
    else:
        st.markdown("**Server status:** connect to your server to check")
    if mod.description:
        st.divider()
        st.markdown(mod.description)
    st.divider()
    action1, action2 = st.columns(2)
    if action1.button(
        "Install on server", type="primary", use_container_width=True, disabled=not can_install
    ):
        st.session_state["queued_install"] = [mod]
        st.rerun()
    if mod.detail_url:
        action2.link_button("Open mod page", mod.detail_url, use_container_width=True)
    if not can_install:
        st.caption("Connect on the Connect page to install mods.")


def human_size_label(label: str) -> str:
    if not label:
        return "-"
    return "unknown (press Load file sizes)" if label == "?" else label


def _toggle_pick(key: str) -> None:
    picks = st.session_state.setdefault("browse_picks", set())
    if st.session_state.get(f"pick::{key}"):
        picks.add(key)
    else:
        picks.discard(key)


def page_browse() -> None:
    if st.session_state.get("connected"):
        connection = (st.session_state["creds"], st.session_state["mods_path"])
    else:
        connection = None

    st.header("Browse and install mods")
    st.caption("Mods are downloaded from the community index at projectdaedalus.app and uploaded straight to your server.")
    if connection is None:
        st.info(
            "You can browse and search freely. Connect on the **Connect** page when you are "
            "ready to install mods to your server."
        )

    author_options = [("", "All authors")] + load_authors()
    with st.form("catalog_search"):
        col1, col2, col3 = st.columns([2, 1, 1])
        query = col1.text_input("Search", placeholder="e.g. stacks, laanp, turret")
        download_type = col2.selectbox("Download type", ["pak", "all", "zip", "exmod"])
        author = col3.selectbox(
            "Author",
            options=author_options,
            format_func=lambda option: option[1],
        )
        searched = st.form_submit_button("Search", type="primary")
    if searched:
        st.session_state["search_page"] = 1
        st.session_state["result_page"] = 1

    page = int(st.session_state.get("search_page", 1))
    try:
        with st.spinner("Fetching mods..."):
            result = load_catalog(query.strip(), download_type, author[0], page)
    except catalog.CatalogError as exc:
        st.error(str(exc))
        return

    if result.total_pages > 1:
        nav1, nav2, nav3 = st.columns([1, 2, 1])
        if nav1.button("Previous", disabled=page <= 1):
            st.session_state["search_page"] = page - 1
            st.rerun()
        nav2.markdown(
            f"<div style='text-align:center'>Page {result.page} of {result.total_pages} "
            f"({result.total_mods} mods)</div>",
            unsafe_allow_html=True,
        )
        if nav3.button("Next", disabled=page >= result.total_pages):
            st.session_state["search_page"] = page + 1
            st.rerun()

    if not result.mods:
        st.info("No mods matched. Try a different search or download type.")
        return

    if connection is not None:
        installed_files = _server_files(connection[0], connection[1])
    else:
        installed_files = []
    exact_names = {entry.name for entry in installed_files}
    base_names = {base_mod_key(entry.name) for entry in installed_files}

    def status_for(mod: catalog.ModEntry) -> str:
        filename = Path(mod.filename).name if mod.filename else ""
        if not filename:
            return ""
        if filename in exact_names:
            return "Installed"
        if base_mod_key(filename) in base_names:
            return "Different version installed"
        return ""

    signature = (query.strip(), download_type, author[0], result.total_mods)
    if st.session_state.get("browse_signature") != signature:
        st.session_state["browse_signature"] = signature
        st.session_state["result_page"] = 1
    total_pages = max(1, math.ceil(len(result.mods) / PAGE_SIZE))
    current_page = min(max(int(st.session_state.get("result_page", 1)), 1), total_pages)
    start_index = (current_page - 1) * PAGE_SIZE
    visible = result.mods[start_index : start_index + PAGE_SIZE]

    picks: set[str] = st.session_state.setdefault("browse_picks", set())
    selected = [mod for mod in result.mods if _mod_key(mod) in picks]

    top_left, top_right = st.columns([3, 2], vertical_alignment="center")
    with top_left:
        shown_to = min(start_index + PAGE_SIZE, len(result.mods))
        st.caption(f"Showing {start_index + 1}-{shown_to} of {len(result.mods)} mods")
    with top_right:
        unknown_sizes = sum(
            1 for mod in result.mods if mod.download_url and _size_label(mod) == "?"
        )
        if unknown_sizes:
            if st.button(f"Load file sizes ({unknown_sizes} unknown)", use_container_width=True):
                progress = st.progress(0.0, text="Loading file sizes...")
                _load_sizes(result.mods, progress)
                st.rerun()

    header = st.columns([0.4, 3.0, 1.0, 0.8, 0.9, 0.5], vertical_alignment="center")
    header[1].markdown('<span class="th">Mod</span>', unsafe_allow_html=True)
    header[2].markdown('<span class="th">Size</span>', unsafe_allow_html=True)
    header[3].markdown('<span class="th">Week</span>', unsafe_allow_html=True)
    header[4].markdown('<span class="th">Type</span>', unsafe_allow_html=True)
    header[5].markdown('<span class="th">Page</span>', unsafe_allow_html=True)

    for mod in visible:
        key = _mod_key(mod)
        row = st.columns([0.4, 3.0, 1.0, 0.8, 0.9, 0.5], vertical_alignment="center")
        row[0].checkbox(
            "Select",
            key=f"pick::{key}",
            value=key in picks,
            on_change=_toggle_pick,
            args=(key,),
            label_visibility="collapsed",
        )
        if row[1].button(
            mod.name, key=f"name::{key}", type="tertiary", use_container_width=True
        ):
            _mod_dialog(mod, status_for(mod), connection is not None)
        size_label = _size_label(mod)
        row[2].markdown(
            f'<span class="dim">{html.escape(size_label)}</span>' if size_label else "-",
            unsafe_allow_html=True,
        )
        row[3].markdown(_week_chip(mod.week), unsafe_allow_html=True)
        row[4].markdown(_type_chip(mod.download_type), unsafe_allow_html=True)
        if mod.detail_url:
            row[5].link_button(
                "",
                mod.detail_url,
                icon=":material/link:",
                help="Open mod page",
                use_container_width=True,
            )

    if total_pages > 1:
        nav1, nav2, nav3 = st.columns([1, 2, 1], vertical_alignment="center")
        if nav1.button("Previous", disabled=current_page <= 1):
            st.session_state["result_page"] = current_page - 1
            st.rerun()
        nav2.markdown(
            f"<div style='text-align:center'>Page {current_page} of {total_pages}</div>",
            unsafe_allow_html=True,
        )
        if nav3.button("Next", disabled=current_page >= total_pages):
            st.session_state["result_page"] = current_page + 1
            st.rerun()

    st.divider()
    foot_left, foot_right = st.columns([3, 2], vertical_alignment="center")
    with foot_left:
        if selected:
            names = ", ".join(mod.name for mod in selected[:3])
            more = f" and {len(selected) - 3} more" if len(selected) > 3 else ""
            st.caption(f"{len(selected)} selected: {names}{more}")
    with foot_right:
        if st.button(
            f"Add {len(selected)} selected mod(s) to server",
            type="primary",
            disabled=not selected,
            use_container_width=True,
        ):
            if connection is None:
                st.info(
                    "Connect to your server on the **Connect** page first, then press this button "
                    "again to install the selected mods."
                )
            else:
                install_entries(selected, connection[0], connection[1])
        if selected and st.button("Clear selection", use_container_width=True):
            for mod in result.mods:
                key = _mod_key(mod)
                picks.discard(key)
                st.session_state.pop(f"pick::{key}", None)
            st.rerun()

    queued = st.session_state.pop("queued_install", None)
    if queued:
        if connection is None:
            st.info("Connect to your server on the **Connect** page to install mods.")
        else:
            install_entries(queued, connection[0], connection[1])

    with st.expander("How mods get to the server"):
        st.markdown(
            "- Click a mod's name for full details; the link icon opens its ProjectDaedalus page.\n"
            "- Tick the checkboxes to select several mods, then press *Add selected mods to server*.\n"
            "- Mods are downloaded from their official release location (usually GitHub).\n"
            "- Archives are unpacked automatically and only `.pak` files are uploaded.\n"
            "- Files land in the server's `Icarus/Content/Paks/mods` folder, then you restart the server."
        )


def install_entries(entries: list[catalog.ModEntry], creds: dict, mods_path: str) -> None:
    st.divider()
    progress = st.progress(0.0, text="Preparing downloads...")
    log_box = st.empty()
    log_lines: list[str] = []

    def log(message: str) -> None:
        log_lines.append(message)
        log_box.markdown("\n".join(f"- {line}" for line in log_lines[-40:]))

    workdir_handle = tempfile.TemporaryDirectory(prefix="icarus_mods_")
    workdir = Path(workdir_handle.name)
    to_upload: list[tuple[Path, str]] = []
    failures: list[str] = []
    data_mods: list = []

    for index, mod in enumerate(entries, start=1):
        if not mod.download_url:
            failures.append(f"{mod.name}: no download link available")
            continue
        filename = Path(mod.filename).name if mod.filename else _basename_from_url(mod.download_url)
        destination = workdir / f"{index:02d}_{filename}"
        progress.progress(0.0, text=f"Downloading {mod.name}...")
        try:
            _download_file(mod.download_url, destination)
        except RuntimeError as exc:
            failures.append(f"{mod.name}: download failed ({exc})")
            log(f"Failed {mod.name}: download failed")
            continue
        try:
            paks = archives.unpack_to_paks(destination, workdir / f"unpack_{index}")
        except archives.ArchiveError as exc:
            data_mod = _try_load_exmod(destination)
            if data_mod is not None:
                data_mods.append(data_mod)
                log(f"Downloaded {mod.name} (EXMOD data mod)")
                continue
            failures.append(f"{mod.name}: {exc}")
            log(f"Failed {mod.name}: {exc}")
            continue
        for pak in paks:
            to_upload.append((pak, pak.name))
        log(f"Downloaded {mod.name} ({len(paks)} pak file(s))")

    if data_mods:
        progress.progress(0.0, text="Merging EXMOD data mods with your game data...")
        converted, conversion_failures = _convert_data_mods(data_mods, workdir, log)
        to_upload.extend(converted)
        failures.extend(conversion_failures)

    uploaded_items: list[tuple[Path, str]] = []
    if to_upload:
        uploaded_items, upload_failures, connection_error = _upload_paks(creds, mods_path, to_upload, progress)
        failures.extend(upload_failures)
        if connection_error:
            failures.append(f"Could not connect to the server: {connection_error}")
        for _, name in uploaded_items:
            log(f"Uploaded {name}")

    progress.progress(1.0, text="Finished")
    workdir_handle.cleanup()
    if uploaded_items:
        _mark_mods_changed()
        st.success(f"Uploaded {len(uploaded_items)} file(s) to `{mods_path}`.")
        _copy_local(uploaded_items)
    for message in failures:
        st.error(message)


def page_upload() -> None:
    connection = require_connection()
    if not connection:
        return
    creds, mods_path = connection

    st.header("Upload mods from this computer")
    st.caption(
        "Already have .pak files, or .zip archives containing them? Add them here and they will be "
        "uploaded to your server's mods folder."
    )

    uploads = st.file_uploader(
        "Mod files",
        type=["pak", "zip", "exmodz", "exmod", "rar"],
        accept_multiple_files=True,
        help="Supported: .pak files, .zip archives containing .pak files, and .EXMODZ data mods "
        "(converted automatically when your local game folder is set).",
    )
    if not uploads:
        return

    workdir_handle = tempfile.TemporaryDirectory(prefix="icarus_upload_")
    workdir = Path(workdir_handle.name)
    ready: list[Path] = []
    problems: list[str] = []
    data_mods: list = []
    for index, upload in enumerate(uploads):
        destination = workdir / f"{index:02d}_{Path(upload.name).name}"
        destination.write_bytes(upload.getbuffer())
        try:
            ready.extend(archives.unpack_to_paks(destination, workdir / f"unpack_{index}"))
        except archives.ArchiveError as exc:
            data_mod = _try_load_exmod(destination)
            if data_mod is not None:
                data_mods.append(data_mod)
                continue
            problems.append(f"{upload.name}: {exc}")

    if data_mods:
        conversion_notes: list[str] = []
        converted, conversion_failures = _convert_data_mods(data_mods, workdir, conversion_notes.append)
        ready.extend(pak for pak, _ in converted)
        problems.extend(conversion_failures)
        for note in conversion_notes:
            st.caption(note)
    for problem in problems:
        st.error(problem)
    if not ready:
        workdir_handle.cleanup()
        return

    st.dataframe(
        [
            {"File": pak.name, "Size": human_size(pak.stat().st_size), "Pak contents": _pak_contents(pak)}
            for pak in ready
        ],
        hide_index=True,
        use_container_width=True,
    )

    if st.button(f"Upload {len(ready)} file(s) to server", type="primary"):
        progress = st.progress(0.0, text="Uploading...")
        uploaded_items, failures, connection_error = _upload_paks(
            creds, mods_path, [(pak, pak.name) for pak in ready], progress
        )
        progress.progress(1.0, text="Finished")
        if uploaded_items:
            _mark_mods_changed()
            st.success(f"Uploaded {len(uploaded_items)} file(s) to `{mods_path}`.")
            _copy_local(uploaded_items)
        for failure in failures:
            st.error(failure)
        if connection_error:
            st.error(f"Connection failed: {connection_error}")
    workdir_handle.cleanup()


def page_installed() -> None:
    connection = require_connection()
    if not connection:
        return
    creds, mods_path = connection

    st.header("Installed mods")
    st.caption(f"Files currently in `{mods_path}`")

    if st.button("Refresh"):
        _server_files(creds, mods_path, force=True)

    files = [entry for entry in _server_files(creds, mods_path) if not entry.is_dir]
    files.sort(key=lambda entry: entry.name.lower())
    if not files:
        st.info("No files in the mods folder yet. Use **Browse Mods** or **Upload Local Files** to add some.")
        return

    rows = [
        {"Name": entry.name, "Size": human_size(entry.size), "Modified": entry.modified or ""}
        for entry in files
    ]
    event = st.dataframe(
        rows,
        hide_index=True,
        use_container_width=True,
        height=min(600, 80 + 35 * len(rows)),
        on_select="rerun",
        selection_mode="multi-row",
    )

    selected = [files[index] for index in event.selection.rows]
    confirm = st.checkbox("I understand these files will be permanently deleted from the server")
    if st.button(
        f"Delete {len(selected)} selected file(s)",
        type="primary",
        disabled=not selected or not confirm,
    ):
        deleted: list[str] = []
        failures: list[str] = []
        try:
            with make_server(creds) as server:
                for entry in selected:
                    try:
                        server.delete(posixpath.join(mods_path, entry.name))
                        deleted.append(entry.name)
                    except RemoteError as exc:
                        failures.append(f"{entry.name}: {exc}")
        except RemoteError as exc:
            st.error(f"Connection failed: {exc}")
        if deleted:
            _mark_mods_changed()
            st.success(f"Deleted {len(deleted)} file(s).")
            st.rerun()
        for failure in failures:
            st.error(failure)


def page_help() -> None:
    st.header("Help")
    st.markdown(
        """
### The quick version
1. Go to **Browse Mods** and look around - no server connection is needed to browse.
   Click a mod's name for its full details, or the link icon on the right to open its
   ProjectDaedalus page.
2. Tick the checkboxes to select the mods you want.
3. Go to **Connect** and enter the FTP/SFTP details from your game server host's control panel.
4. Back on **Browse Mods**, press **Add selected mods to server**.
5. Restart your server from the host's control panel so it loads the new mods.

### Where mods are installed
Icarus dedicated servers load `.pak` mods from:

```
Icarus/Content/Paks/mods
```

The app finds that folder automatically (even on hosts that put your files inside a
config number folder). If auto-detection fails, open your host's file manager, find the
`Icarus/Content/Paks` folder, and enter its `mods` path manually on the Connect page.

### After installing mods
- Restart the server so it picks up new files.
- Every connecting player must install the same mods in their own local game
  (`steamapps/common/Icarus/Icarus/Content/Paks/mods`), otherwise they can get errors
  or disconnects.

### Copying mods to your own game automatically
On the Connect page, set your local mods folder (the app detects the usual Steam location).
After that, every mod you upload to the server is also copied into your own
`Icarus/Content/Paks/mods` folder, and you can toggle this with
*Also install mods to my local game* in the sidebar. Friends can download the same mods
from the Browse Mods page (or you can share the `.pak` files with them).

### Supported files
| File | Supported | Notes |
|---|---|---|
| `.pak` | Yes | The standard mod format, uploaded as-is |
| `.zip` | Yes | `.pak` files inside are extracted and uploaded |
| `.ucas` / `.utoc` | Yes | Uploaded alongside the `.pak` that ships with them |
| `.EXMODZ` | Yes | Converted automatically using your local game data (see below) |
| `.EXMOD` | Yes | Same as EXMODZ, unzipped; also converted automatically |
| `.rar` | No | Extract it with 7-Zip or WinRAR and upload the `.pak` |

### EXMODZ data mods are converted for you
EXMODZ packages contain row-level edits to the game's data tables ("change Wood's
stack size from 100 to 200"). Icarus can only load `.pak` files, so the app reads the
current base data straight from your local Icarus install, merges the changes, and
builds a `_P.pak` that is uploaded to the server (and copied to your game, like any
other mod). This requires:

- Icarus installed on this computer, with the local game folder set on the Connect page
- Your local game on the same weekly update as the server

When several EXMOD mods are installed in one go they are merged into a single pak;
if two mods change the same row, the later one wins (same behavior as Icarus Mod
Manager). Files that do not exist in your game version are skipped and reported.

### Connection protocols
- **FTP** is the default on most game server hosts.
- **FTPS** is explicit TLS. If you get a protocol error, try plain FTP or SFTP.
- **SFTP** is SSH file transfer, used by some hosts (for example BisectHosting).
  The app trusts the server's host key on first connect, like any simple SFTP client.

### Privacy
Connection settings (protocol, host, port, username, folder path) and your local game
folder are saved to `~/.icarus_server_mod_manager/config.json` only if you leave the
remember checkbox on. The password is never written to disk.

### Credits
Mod index: community database at
[projectdaedalus.app](https://www.projectdaedalus.app). Mods are downloaded from
their original release links.
"""
    )


def render_sidebar() -> str:
    with st.sidebar:
        st.title("Icarus Mod Manager")
        st.caption("Dedicated-server mods, without the FTP client.")
        page = st.radio("Navigation", PAGES, label_visibility="collapsed")
        st.divider()
        if st.session_state.get("connected"):
            st.caption("Connected")
            st.write(st.session_state["server_label"])
            st.code(st.session_state["mods_path"], language=None)
        else:
            st.caption("Not connected")
        st.divider()
        if st.session_state.get("local_mods_path"):
            st.caption("Local game folder")
            st.code(st.session_state["local_mods_path"], language=None)
            st.checkbox(
                "Also install mods to my local game",
                key="copy_to_local",
                help="Uploaded mods are copied into your own Icarus game folder.",
            )
        else:
            st.caption("Local game folder not set (see Connect page)")
        st.divider()
        st.caption(f"v{__version__} - mods indexed by projectdaedalus.app")
    return page


def _bootstrap_state() -> None:
    st.session_state.setdefault("profile", settings.load_profile())
    st.session_state.setdefault("local_mods_path", st.session_state["profile"].get("local_mods_path", ""))
    st.session_state.setdefault("copy_to_local", True)
    st.session_state.setdefault("detected_local_path", None)
    st.session_state.setdefault("connected", False)
    st.session_state.setdefault("creds", None)
    st.session_state.setdefault("mods_path", None)
    st.session_state.setdefault("server_label", "")
    st.session_state.setdefault("pending_restart", False)
    st.session_state.setdefault("search_page", 1)
    st.session_state.setdefault("server_files", None)
    st.session_state.setdefault("server_files_at", 0.0)


def main() -> None:
    _bootstrap_state()
    _inject_theme()
    page = render_sidebar()
    _pending_restart_banner()
    if page == "Connect":
        page_connect()
    elif page == "Browse Mods":
        page_browse()
    elif page == "Upload Local Files":
        page_upload()
    elif page == "Installed Mods":
        page_installed()
    else:
        page_help()


main()
