"""A lock pathname replaced by a symlink while waiting for flock fails closed."""
import fcntl
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX required')
class JournalPostAcquireSymlinkTests(unittest.TestCase):
    def test_same_inode_symlink_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            sidecar = Path(str(path) + '.lock')
            moved = Path(tmp) / 'original-lock'
            real_flock = fcntl.flock

            def replace_on_lock(fd, operation):
                result = real_flock(fd, operation)
                if operation == fcntl.LOCK_EX:
                    sidecar.rename(moved)
                    sidecar.symlink_to(moved)
                return result

            with patch('services.exchange.command_log.fcntl.flock', side_effect=replace_on_lock):
                with self.assertRaisesRegex(JournalError, 'lock file identity changed'):
                    CommandJournal(path).append(1, {'id': 'one'})
            self.assertFalse(path.exists())
            self.assertTrue(sidecar.is_symlink())
            self.assertEqual(os.stat(sidecar).st_ino, os.stat(moved).st_ino)
            self.assertEqual(os.stat(moved).st_nlink, 1)

    def test_normal_lock_still_supports_append_and_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {'id': 'one'}))
            self.assertFalse(journal.append(1, {'id': 'one'}))
            self.assertEqual(len(CommandJournal(path).entries()), 1)


if __name__ == '__main__':
    unittest.main()
