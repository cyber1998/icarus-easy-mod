import logging
import tempfile
import threading
import unittest
from pathlib import Path

logging.getLogger("pyftpdlib").setLevel(logging.CRITICAL)

from icarus_manager.remote import FtpServer, RemoteError, ensure_mods_dir, find_icarus_root

try:
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer

    HAVE_PYFTPDLIB = True
except ImportError:
    HAVE_PYFTPDLIB = False


@unittest.skipUnless(HAVE_PYFTPDLIB, "pyftpdlib not installed (pip install -r requirements-dev.txt)")
class FtpServerTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        authorizer = DummyAuthorizer()
        authorizer.add_user("user", "pass", self.home.name, perm="elradfmwMT")
        handler = FTPHandler
        handler.authorizer = authorizer
        self.server = FTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.socket.getsockname()[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"timeout": 0.2}, daemon=True
        )
        self.thread.start()

    def tearDown(self):
        self.server.close_all()
        self.thread.join(timeout=5)
        self.home.cleanup()

    def _connect(self):
        return FtpServer(host="127.0.0.1", port=self.port, username="user", password="pass")

    def test_login_failure_raises_friendly_error(self):
        with self.assertRaises(RemoteError):
            with FtpServer(host="127.0.0.1", port=self.port, username="user", password="wrong"):
                pass

    def test_directory_creation_and_listing(self):
        with self._connect() as server:
            mods_path = ensure_mods_dir(server, "/Icarus")
            self.assertEqual(mods_path, "/Icarus/Content/Paks/mods")
            entries = server.list_dir("/Icarus/Content/Paks")
            self.assertIn("mods", [entry.name for entry in entries])

    def test_find_icarus_root(self):
        with self._connect() as server:
            with self.assertRaises(RemoteError):
                find_icarus_root(server)
            server.mkdirs("/Icarus/Content/Paks/mods")
            self.assertEqual(find_icarus_root(server), "/Icarus")

    def test_find_icarus_root_nested_config_folder(self):
        with self._connect() as server:
            server.mkdirs("/123456/Icarus/Content/Paks")
            self.assertEqual(find_icarus_root(server), "/123456/Icarus")

    def test_upload_list_exists_delete(self):
        payload = b"0" * (300 * 1024)
        local = Path(self.home.name).parent / "upload_test_P.pak"
        local.write_bytes(payload)
        try:
            with self._connect() as server:
                mods_path = ensure_mods_dir(server, "/Icarus")
                remote = f"{mods_path}/upload_test_P.pak"
                calls = []
                server.upload_file(str(local), remote, lambda done, total: calls.append((done, total)))
                self.assertTrue(calls)
                self.assertEqual(calls[-1][0], len(payload))

                self.assertTrue(server.exists(remote))
                entry = next(e for e in server.list_dir(mods_path) if e.name == "upload_test_P.pak")
                self.assertEqual(entry.size, len(payload))

                server.delete(remote)
                self.assertFalse(server.exists(remote))
                self.assertEqual(server.list_dir(mods_path), [])
        finally:
            local.unlink(missing_ok=True)

    def test_upload_to_missing_folder_raises(self):
        local = Path(self.home.name) / "missing_P.pak"
        local.write_bytes(b"x")
        with self._connect() as server:
            with self.assertRaises(RemoteError):
                server.upload_file(str(local), "/nope/missing_P.pak")


if __name__ == "__main__":
    unittest.main()
