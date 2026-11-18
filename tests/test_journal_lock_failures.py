"""POSIX lock failure injection for CommandJournal (not a crash-safety test)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


@unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"), "POSIX O_NOFOLLOW required")
class JournalLockFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "commands.log"
        self.journal = CommandJournal(self.path)

    def test_normal_append_and_idempotent_retry(self):
        self.assertTrue(self.journal.append(1, {"type": "test"}))
        self.assertFalse(self.journal.append(1, {"type": "test"}))
        self.assertEqual(len(CommandJournal(self.path).entries()), 1)

    def test_fstat_failure_does_not_append(self):
        with patch("services.exchange.command_log.os.fstat", side_effect=OSError("injected fstat")):
            with self.assertRaises(JournalError):
                self.journal.append(1, {"type": "test"})
        self.assertEqual(CommandJournal(self.path).entries(), ())

    def test_fstat_failure_closes_sidecar_descriptor_and_poisoned_instance(self):
        # Capture the real descriptor, then fail the first stat on the sidecar.
        # This checks ownership/cleanup rather than merely checking disk bytes.
        real_fstat = os.fstat
        descriptors = []

        def injected_fstat(fd):
            descriptors.append(fd)
            raise OSError("injected sidecar stat")

        with patch("services.exchange.command_log.os.fstat", side_effect=injected_fstat):
            with self.assertRaises(JournalError):
                self.journal.append(1, {"type": "test"})
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            real_fstat(descriptors[0])
        with self.assertRaises(JournalError):
            self.journal.append(1, {"type": "test"})
        self.assertEqual(CommandJournal(self.path).entries(), ())

    def test_lock_acquisition_failure_does_not_append(self):
        with patch("services.exchange.command_log.fcntl.flock", side_effect=OSError("injected lock")):
            with self.assertRaises(JournalError):
                self.journal.append(1, {"type": "test"})
        self.assertEqual(CommandJournal(self.path).entries(), ())

    def test_unlock_failure_requires_reconciliation(self):
        import fcntl
        original = fcntl.flock

        def injected(fd, operation):
            if operation == fcntl.LOCK_UN:
                raise OSError("injected unlock")
            return original(fd, operation)

        with patch("services.exchange.command_log.fcntl.flock", side_effect=injected):
            with self.assertRaises(JournalError):
                self.journal.append(1, {"type": "test"})
        self.assertEqual(len(CommandJournal(self.path).entries()), 1)
        with self.assertRaises(JournalError):
            self.journal.append(2, {"type": "second"})


if __name__ == "__main__":
    unittest.main()
