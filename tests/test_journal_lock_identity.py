import fcntl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from services.exchange.command_log import CommandJournal, JournalError

class LockIdentityTests(unittest.TestCase):
    def test_sidecar_replaced_during_lock_acquisition_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            journal = CommandJournal(path)
            lock_path = Path(str(path) + '.lock')
            real_flock = fcntl.flock
            def replace_after_lock(fd, operation):
                real_flock(fd, operation)
                if operation == fcntl.LOCK_EX:
                    lock_path.unlink()
                    lock_path.touch()
            with patch('services.exchange.command_log.fcntl.flock', side_effect=replace_after_lock):
                with self.assertRaisesRegex(JournalError, 'lock file identity changed'):
                    journal.append(1, {'id': 'one'})
            self.assertFalse(path.exists())
            self.assertTrue(CommandJournal(path).append(1, {'id': 'recovered'}))

    def test_unmodified_lock_allows_append_and_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = CommandJournal(Path(tmp) / 'journal')
            self.assertTrue(journal.append(1, {'id': 'one'}))
            self.assertFalse(journal.append(1, {'id': 'one'}))
            self.assertEqual(len(journal.entries()), 1)

    def test_sidecar_deleted_during_lock_acquisition_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            journal = CommandJournal(path)
            lock_path = Path(str(path) + '.lock')
            real_flock = fcntl.flock
            def delete_after_lock(fd, operation):
                real_flock(fd, operation)
                if operation == fcntl.LOCK_EX:
                    lock_path.unlink()
            with patch('services.exchange.command_log.fcntl.flock', side_effect=delete_after_lock):
                with self.assertRaisesRegex(JournalError, 'lock file identity changed'):
                    journal.append(1, {'id': 'one'})
            self.assertFalse(path.exists())
