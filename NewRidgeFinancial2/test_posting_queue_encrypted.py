"""Posting queue works with SQLCipher-encrypted nr2.sqlite3."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


class PostingQueueEncryptedDbTests(unittest.TestCase):
    def test_list_entries_on_encrypted_store(self) -> None:
        try:
            import sqlcipher3  # noqa: F401
        except ImportError:
            try:
                import pysqlcipher3  # noqa: F401
            except ImportError:
                self.skipTest("sqlcipher3/pysqlcipher3 not installed")
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            with mock.patch.dict("os.environ", {"NR2_DB_ENCRYPTION": "1"}, clear=False):
                from local_store import LocalStore
                from posting_queue_store import PostingQueueStore

                store = LocalStore(data_dir)
                pq = PostingQueueStore(store.db_path)
                entries = pq.list_entries(limit=5)
                self.assertIsInstance(entries, list)


if __name__ == "__main__":
    unittest.main()
