"""A substituted lock sidecar must not block on a FIFO or lock a device."""
import os
import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError


@unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW") and hasattr(os, "mkfifo"), "POSIX required")
class JournalLockFileTypeTests(unittest.TestCase):
    def test_fifo_sidecar_fails_without_blocking_or_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            os.mkfifo(str(path) + ".lock")
            with self.assertRaisesRegex(JournalError, "must be regular"):
                CommandJournal(path).append(1, {"id": "one"})
            self.assertFalse(path.exists())

    def test_directory_sidecar_fails_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            Path(str(path) + ".lock").mkdir()
            with self.assertRaises(JournalError):
                CommandJournal(path).append(1, {"id": "one"})
            self.assertFalse(path.exists())

    def test_regular_sidecar_still_allows_replay_and_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {"id": "one"}))
            self.assertFalse(journal.append(1, {"id": "one"}))
            self.assertEqual(CommandJournal(path).entries(), ({"sequence": 1, "payload": {"id": "one"}},))


if __name__ == "__main__":
    unittest.main()
