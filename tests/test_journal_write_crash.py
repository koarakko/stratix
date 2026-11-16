"""Process-death fault injection at journal write boundaries (POSIX only)."""
import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


def _crash_during_write(path, partial):
    """Exit without cleanup after a partial or full actual OS write."""
    journal = CommandJournal(path)
    real_write = os.write

    def write_then_die(fd, data):
        real_write(fd, data[:len(data) // 2] if partial else data)
        os._exit(73)

    with patch('services.exchange.command_log.os.write', side_effect=write_then_die):
        journal.append(2, {'id': 'pending'})
    os._exit(74)  # Never reached if the injection works.


class JournalWriteCrashTests(unittest.TestCase):
    def _run_crash(self, path, partial):
        ctx = multiprocessing.get_context('spawn')
        process = ctx.Process(target=_crash_during_write, args=(path, partial))
        process.start()
        try:
            process.join(10)
            self.assertFalse(process.is_alive(), 'write worker timed out')
            self.assertEqual(process.exitcode, 73, 'worker did not reach injected crash')
        finally:
            if process.is_alive():
                process.terminate()
            process.join(10)

    def test_partial_write_crash_fails_closed_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'commands'
            self.assertTrue(CommandJournal(path).append(1, {'id': 'committed'}))
            original = path.read_bytes()
            self._run_crash(path, partial=True)
            damaged = path.read_bytes()
            self.assertTrue(damaged.startswith(original))
            self.assertGreater(len(damaged), len(original))
            with self.assertRaisesRegex(JournalError, 'incomplete trailing record'):
                CommandJournal(path)
            self.assertEqual(path.read_bytes(), damaged, 'recovery must not truncate')

    def test_complete_write_before_fsync_is_ambiguous_not_new_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'commands'
            self.assertTrue(CommandJournal(path).append(1, {'id': 'committed'}))
            self._run_crash(path, partial=False)
            reopened = CommandJournal(path)
            self.assertEqual([entry['sequence'] for entry in reopened.entries()], [1, 2])
            self.assertFalse(reopened.append(2, {'id': 'pending'}))
            with self.assertRaisesRegex(JournalError, 'conflicting committed sequence'):
                reopened.append(2, {'id': 'other'})
            self.assertTrue(reopened.append(3, {'id': 'next'}))
            self.assertEqual(len(CommandJournal(path).entries()), 3)


if __name__ == '__main__':
    unittest.main()
