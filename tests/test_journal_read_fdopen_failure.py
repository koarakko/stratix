"""Read-side descriptor ownership fault injection (not crash testing)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


@unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"), "POSIX O_NOFOLLOW required")
class JournalReadFdopenFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "journal"
        self.journal = CommandJournal(self.path)
        self.assertTrue(self.journal.append(1, {"type": "test"}))

    def test_read_fdopen_failure_closes_raw_fd_and_preserves_history(self):
        real_fdopen = os.fdopen
        real_close = os.close
        opened = []
        closed = []

        def fail_read(fd, mode, *args, **kwargs):
            if mode == "rb":
                opened.append(fd)
                raise OSError("injected fdopen failure")
            return real_fdopen(fd, mode, *args, **kwargs)

        def track_close(fd):
            closed.append(fd)
            return real_close(fd)

        before = self.path.read_bytes()
        with patch("services.exchange.command_log.os.fdopen", side_effect=fail_read), patch(
            "services.exchange.command_log.os.close", side_effect=track_close
        ):
            with self.assertRaisesRegex(JournalError, "descriptor wrapping failed"):
                self.journal.entries()
        self.assertEqual(len(opened), 1)
        self.assertIn(opened[0], closed)
        with self.assertRaises(OSError):
            os.fstat(opened[0])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.journal.entries()[0]["sequence"], 1)
        self.assertFalse(self.journal.append(1, {"type": "test"}))

    def test_initialization_fdopen_failure_closes_descriptor(self):
        original = os.fdopen
        seen = []
        def fail_read(fd, mode, *args, **kwargs):
            if mode == "rb":
                seen.append(fd)
                raise OSError("injected")
            return original(fd, mode, *args, **kwargs)
        with patch("services.exchange.command_log.os.fdopen", side_effect=fail_read):
            with self.assertRaises(JournalError):
                CommandJournal(self.path)
        self.assertEqual(len(seen), 1)
        with self.assertRaises(OSError):
            os.fstat(seen[0])
        self.assertEqual(len(CommandJournal(self.path).entries()), 1)

    def test_normal_reopen_and_next_append(self):
        reopened = CommandJournal(self.path)
        self.assertEqual(reopened.entries(), ({"sequence": 1, "payload": {"type": "test"}},))
        self.assertTrue(reopened.append(2, {"type": "next"}))
        self.assertEqual(len(CommandJournal(self.path).entries()), 2)
