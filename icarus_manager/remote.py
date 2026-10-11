"""Remote server access over FTP, FTPS (explicit TLS) or SFTP."""

from __future__ import annotations

import ftplib
import os
import posixpath
import socket
import stat as stat_module
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

try:
    import paramiko
except ImportError:  # pragma: no cover
    paramiko = None

ProgressCallback = Callable[[int, int], None]
UPLOAD_BLOCK_SIZE = 64 * 1024
SKIP_DIRS = {"lost+found", "$recycle.bin", "recycler", "system volume information"}


class RemoteError(Exception):
    """User-readable connection or file operation error."""


@dataclass
class RemoteFile:
    name: str
    size: int
    modified: Optional[str]
    is_dir: bool


class RemoteServer:
    protocol = "remote"

    def __enter__(self) -> "RemoteServer":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False

    def connect(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def home(self) -> str:
        raise NotImplementedError

    def list_dir(self, path: str) -> list[RemoteFile]:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        raise NotImplementedError

    def mkdirs(self, path: str) -> None:
        raise NotImplementedError

    def upload_file(
        self, local_path: str, remote_path: str, progress_cb: Optional[ProgressCallback] = None
    ) -> None:
        raise NotImplementedError

    def delete(self, path: str) -> None:
        raise NotImplementedError

    @property
    def description(self) -> str:
        return f"{self.protocol.upper()} {self.host}:{self.port}"


class FtpServer(RemoteServer):
    def __init__(
        self,
        host: str,
        port: Optional[int] = None,
        username: str = "anonymous",
        password: str = "",
        tls: bool = False,
        timeout: int = 30,
    ) -> None:
        self.host = host
        self.port = int(port or 21)
        self.username = username
        self.password = password
        self.tls = tls
        self.timeout = timeout
        self._ftp: Optional[ftplib.FTP] = None

    @property
    def protocol(self) -> str:
        return "ftps" if self.tls else "ftp"

    def connect(self) -> None:
        try:
            ftp = ftplib.FTP_TLS(timeout=self.timeout) if self.tls else ftplib.FTP(timeout=self.timeout)
            ftp.connect(self.host, self.port)
            ftp.login(self.username, self.password)
            if self.tls:
                ftp.prot_p()
            ftp.set_pasv(True)
            self._ftp = ftp
        except ftplib.error_perm as exc:
            message = str(exc)
            if message.startswith("530"):
                raise RemoteError("Login failed: check the username and password from your host's panel.") from exc
            if message.startswith("534") or message.startswith("500"):
                raise RemoteError(
                    "This server does not accept the selected protocol. "
                    "Try plain FTP or SFTP instead of FTPS."
                ) from exc
            raise RemoteError(f"Server refused the connection: {message}") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise RemoteError(
                f"Timed out connecting to {self.host}:{self.port}. Check the host and port."
            ) from exc
        except (OSError, EOFError) as exc:
            raise RemoteError(
                f"Could not reach {self.host}:{self.port}: {exc}. "
                "Check the address, port and your internet connection."
            ) from exc

    def close(self) -> None:
        if self._ftp is None:
            return
        try:
            self._ftp.quit()
        except Exception:
            try:
                self._ftp.close()
            except Exception:
                pass
        finally:
            self._ftp = None

    def _require(self) -> ftplib.FTP:
        if self._ftp is None:
            raise RemoteError("Not connected.")
        return self._ftp

    def home(self) -> str:
        try:
            return self._require().pwd() or "/"
        except ftplib.all_errors:
            return "/"

    def list_dir(self, path: str) -> list[RemoteFile]:
        ftp = self._require()
        entries: list[RemoteFile] = []
        try:
            for name, facts in ftp.mlsd(path, facts=["type", "size", "modify"]):
                if name in (".", ".."):
                    continue
                is_dir = facts.get("type") in ("dir", "cdir", "pdir")
                try:
                    size = int(facts.get("size") or 0)
                except (TypeError, ValueError):
                    size = 0
                modify = facts.get("modify")
                if modify and len(modify) == 14 and modify.isdigit():
                    modify = f"{modify[0:4]}-{modify[4:6]}-{modify[6:8]} {modify[8:10]}:{modify[10:12]}"
                entries.append(RemoteFile(name, size, modify, is_dir))
            return entries
        except ftplib.error_perm:
            pass
        try:
            names = ftp.nlst(path)
        except ftplib.error_perm as exc:
            raise RemoteError(f"Cannot list '{path}' on the server: {exc}") from exc
        for full in names:
            base = posixpath.basename(str(full).rstrip("/"))
            if not base or base in (".", ".."):
                continue
            child = posixpath.join(path, base)
            entries.append(RemoteFile(base, 0, None, self._is_dir(child)))
        return entries

    def _is_dir(self, path: str) -> bool:
        ftp = self._require()
        try:
            previous = ftp.pwd()
        except ftplib.all_errors:
            previous = "/"
        try:
            ftp.cwd(path)
        except ftplib.all_errors:
            return False
        try:
            ftp.cwd(previous)
        except ftplib.all_errors:
            pass
        return True

    def exists(self, path: str) -> bool:
        normalized = path.rstrip("/")
        if not normalized:
            return True
        parent = posixpath.dirname(normalized) or "/"
        name = posixpath.basename(normalized)
        try:
            return any(entry.name == name for entry in self.list_dir(parent))
        except RemoteError:
            return False

    def mkdirs(self, path: str) -> None:
        ftp = self._require()
        normalized = path.replace("\\", "/")
        if not normalized.startswith("/"):
            normalized = "/" + normalized
        current = ""
        for part in (p for p in normalized.split("/") if p):
            current += "/" + part
            try:
                ftp.mkd(current)
            except ftplib.error_perm:
                if not self._is_dir(current):
                    raise RemoteError(
                        f"Cannot create remote folder '{current}'. "
                        "The account may not have write permission there."
                    ) from None

    def upload_file(
        self, local_path: str, remote_path: str, progress_cb: Optional[ProgressCallback] = None
    ) -> None:
        ftp = self._require()
        total = os.path.getsize(local_path)
        sent = 0

        def _callback(block: bytes) -> None:
            nonlocal sent
            sent += len(block)
            if progress_cb:
                progress_cb(sent, total)

        try:
            with open(local_path, "rb") as handle:
                ftp.storbinary(f"STOR {remote_path}", handle, blocksize=UPLOAD_BLOCK_SIZE, callback=_callback)
        except ftplib.error_perm as exc:
            raise RemoteError(f"Upload refused for '{posixpath.basename(remote_path)}': {exc}") from exc
        except (OSError, EOFError) as exc:
            raise RemoteError(f"Upload interrupted for '{posixpath.basename(remote_path)}': {exc}") from exc

    def delete(self, path: str) -> None:
        try:
            self._require().delete(path)
        except ftplib.error_perm as exc:
            raise RemoteError(f"Could not delete '{posixpath.basename(path)}': {exc}") from exc


class SftpServer(RemoteServer):
    def __init__(
        self,
        host: str,
        port: Optional[int] = None,
        username: str = "",
        password: str = "",
        timeout: int = 30,
    ) -> None:
        self.host = host
        self.port = int(port or 22)
        self.username = username
        self.password = password
        self.timeout = timeout
        self._client = None
        self._sftp = None

    @property
    def protocol(self) -> str:
        return "sftp"

    def connect(self) -> None:
        if paramiko is None:
            raise RemoteError("SFTP support needs the 'paramiko' package. Install it with: pip install paramiko")
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                banner_timeout=self.timeout,
                auth_timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            self._client = client
            self._sftp = client.open_sftp()
        except paramiko.AuthenticationException as exc:
            raise RemoteError("Login failed: check the username and password from your host's panel.") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise RemoteError(f"Timed out connecting to {self.host}:{self.port}.") from exc
        except paramiko.SSHException as exc:
            raise RemoteError(f"SSH error while connecting: {exc}") from exc
        except OSError as exc:
            raise RemoteError(
                f"Could not reach {self.host}:{self.port}: {exc}. "
                "Check the address, port and your internet connection."
            ) from exc

    def close(self) -> None:
        if self._sftp is not None:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def _require(self):
        if self._sftp is None:
            raise RemoteError("Not connected.")
        return self._sftp

    def home(self) -> str:
        try:
            return self._require().normalize(".") or "."
        except OSError:
            return "."

    def list_dir(self, path: str) -> list[RemoteFile]:
        sftp = self._require()
        try:
            attrs = sftp.listdir_attr(path)
        except OSError as exc:
            raise RemoteError(f"Cannot list '{path}' on the server: {exc}") from exc
        entries: list[RemoteFile] = []
        for attr in attrs:
            modified = None
            if attr.st_mtime:
                modified = datetime.fromtimestamp(attr.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            entries.append(
                RemoteFile(
                    attr.filename,
                    int(attr.st_size or 0),
                    modified,
                    stat_module.S_ISDIR(attr.st_mode or 0),
                )
            )
        return entries

    def exists(self, path: str) -> bool:
        try:
            self._require().stat(path)
            return True
        except OSError:
            return False

    def _dir_exists(self, path: str) -> bool:
        try:
            attr = self._require().stat(path)
        except OSError:
            return False
        return stat_module.S_ISDIR(attr.st_mode or 0)

    def mkdirs(self, path: str) -> None:
        sftp = self._require()
        normalized = path.replace("\\", "/")
        parts = [p for p in normalized.split("/") if p]
        current = "/" if normalized.startswith("/") else ""
        for part in parts:
            current = posixpath.join(current, part) if current else part
            try:
                sftp.mkdir(current)
            except OSError:
                if not self._dir_exists(current):
                    raise RemoteError(
                        f"Cannot create remote folder '{current}'. "
                        "The account may not have write permission there."
                    ) from None

    def upload_file(
        self, local_path: str, remote_path: str, progress_cb: Optional[ProgressCallback] = None
    ) -> None:
        sftp = self._require()
        try:
            sftp.put(local_path, remote_path, callback=progress_cb)
        except OSError as exc:
            raise RemoteError(f"Upload failed for '{posixpath.basename(remote_path)}': {exc}") from exc

    def delete(self, path: str) -> None:
        try:
            self._require().remove(path)
        except OSError as exc:
            raise RemoteError(f"Could not delete '{posixpath.basename(path)}': {exc}") from exc


def _has_content_dir(server: RemoteServer, path: str) -> bool:
    try:
        return any(entry.is_dir and entry.name.lower() == "content" for entry in server.list_dir(path))
    except RemoteError:
        return False


def find_icarus_root(server: RemoteServer, max_depth: int = 3) -> str:
    """Locate the 'Icarus' game directory on the server (breadth-first, shallowest match)."""
    start = server.home() or "/"
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    seen: set[str] = set()
    while queue:
        path, depth = queue.popleft()
        if path in seen:
            continue
        seen.add(path)
        try:
            entries = server.list_dir(path)
        except RemoteError:
            continue
        dirs = sorted((e for e in entries if e.is_dir and e.name not in (".", "..")), key=lambda e: e.name.lower())
        for entry in dirs:
            if entry.name.lower() == "icarus":
                candidate = posixpath.join(path, entry.name)
                if _has_content_dir(server, candidate):
                    return candidate
        if depth >= max_depth:
            continue
        for entry in dirs:
            if entry.name.startswith(".") or entry.name.lower() in SKIP_DIRS:
                continue
            queue.append((posixpath.join(path, entry.name), depth + 1))
    raise RemoteError(
        "Could not find the Icarus game folder on the server. "
        "Open your host's file manager, note the full path to 'Icarus/Content/Paks', "
        "and enter the mods folder path manually on the Connect page."
    )


def ensure_mods_dir(server: RemoteServer, icarus_root: str) -> str:
    mods_path = posixpath.join(icarus_root.rstrip("/"), "Content", "Paks", "mods")
    server.mkdirs(mods_path)
    return mods_path


def list_mod_files(server: RemoteServer, mods_path: str) -> list[RemoteFile]:
    return [entry for entry in server.list_dir(mods_path) if not entry.is_dir]
