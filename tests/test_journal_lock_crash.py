"""POSIX process-death regression for the local advisory journal lock."""
import fcntl
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError


def _hold_lock(path, ready):
    with open(str(path) + '.lock', 'a+b') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        ready.set()
        # Parent terminates this worker while it owns the lock.
        multiprocessing.Event().wait(30)


class JournalLockCrashTests(unittest.TestCase):
    def test_killed_lock_holder_releases_lock_without_mutating_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {'id': 'committed'}))
            original = path.read_bytes()
            ctx = multiprocessing.get_context('spawn')
            ready = ctx.Event()
            holder = ctx.Process(target=_hold_lock, args=(path, ready))
            holder.start()
            try:
                self.assertTrue(ready.wait(10), 'holder did not acquire lock')
                holder.terminate()
                holder.join(10)
                self.assertFalse(holder.is_alive(), 'holder failed to terminate')
                self.assertNotEqual(holder.exitcode, 0)
                self.assertEqual(path.read_bytes(), original)
                reopened = CommandJournal(path)
                self.assertFalse(reopened.append(1, {'id': 'committed'}))
                with self.assertRaisesRegex(JournalError, 'conflicting committed sequence'):
                    reopened.append(1, {'id': 'different'})
                self.assertTrue(reopened.append(2, {'id': 'next'}))
                self.assertEqual([x['sequence'] for x in CommandJournal(path).entries()], [1, 2])
            finally:
                if holder.is_alive():
                    holder.terminate()
                holder.join(10)


if __name__ == '__main__':
    unittest.main()
