from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory.credentials import CredentialStore, dpapi


class CredentialTests(unittest.TestCase):
    def test_encrypted_atomic_storage_replace_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(directory)
            with patch("wechat_memory.credentials.dpapi", return_value=b"encrypted-only"):
                store.save("test-only-key")
            self.assertEqual(store.path.read_bytes(), b"encrypted-only")
            self.assertNotIn("test-only-key", str(store.status()))
            with patch("wechat_memory.credentials.dpapi", return_value=b"test-only-key"):
                self.assertEqual(CredentialStore(directory).load(), "test-only-key")
            with patch("wechat_memory.credentials.dpapi", side_effect=ValueError("failed")):
                with self.assertRaises(ValueError):
                    store.save("new-test-key")
            self.assertEqual(store.path.read_bytes(), b"encrypted-only")
            self.assertFalse(store.delete()["saved"])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_invalid_key_never_written(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(directory)
            with patch("wechat_memory.credentials.dpapi") as encrypt:
                for key in (None, "", "a\nsecret-key"):
                    with self.assertRaises(ValueError):
                        store.save(key)
                encrypt.assert_not_called()
            self.assertFalse(store.status()["saved"])
            with self.assertRaises(ValueError):
                store.load()

    @unittest.skipUnless(sys.platform == "win32", "DPAPI requires Windows")
    def test_real_windows_dpapi_roundtrip_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(directory)
            store.save("test-only-fake-key")
            self.assertNotIn(b"test-only-fake-key", store.path.read_bytes())
            self.assertEqual(CredentialStore(directory).load(), "test-only-fake-key")
            store.save("replacement-fake-key")
            self.assertEqual(CredentialStore(directory).load(), "replacement-fake-key")
            store.delete()

    @unittest.skipIf(sys.platform == "win32", "non-Windows fallback")
    def test_no_plaintext_fallback(self):
        with self.assertRaises(ValueError):
            dpapi(b"test-only-key")
