"""Reject symbolic-link substitution of the cooperative lock sidecar."""
import os
import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError


@unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"), "requires POSIX O_NOFOLLOW")
class JournalLockSymlinkTests(unittest.TestCase):
    def test_symlink_to_existing_file_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            target = Path(tmp) / "unrelated"
            target.write_bytes(b"keep-me")
            (Path(str(path) + ".lock")).symlink_to(target)
            journal = CommandJournal(path)
            with self.assertRaisesRegex(JournalError, "cannot safely open journal lock file"):
                journal.append(1, {"id": "one"})
            self.assertEqual(target.read_bytes(), b"keep-me")
            self.assertFalse(path.exists())

    def test_dangling_symlink_rejected_without_creating_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            missing = Path(tmp) / "missing"
            Path(str(path) + ".lock").symlink_to(missing)
            with self.assertRaises(JournalError):
                CommandJournal(path).append(1, {"id": "one"})
            self.assertFalse(missing.exists())
            self.assertFalse(path.exists())

    def test_regular_sidecar_preserves_append_and_idempotent_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {"id": "one"}))
            self.assertFalse(journal.append(1, {"id": "one"}))
            self.assertEqual(CommandJournal(path).entries(), ({"sequence": 1, "payload": {"id": "one"}},))


if __name__ == "__main__":
    unittest.main()
