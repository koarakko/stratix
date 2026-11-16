import multiprocessing
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


def worker(path, ready, release):
    import fcntl
    with open(str(path) + '.lock', 'a+b') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        ready.set()
        release.wait(5)


class JournalLockTests(unittest.TestCase):
    def test_concurrent_writer_rejected_after_lock_revalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            a = CommandJournal(path)
            b = CommandJournal(path)
            self.assertTrue(a.append(1, {'id': 'one'}))
            with self.assertRaises(JournalError):
                b.append(1, {'id': 'other'})
            self.assertEqual(len(CommandJournal(path).entries()), 1)

    def test_lock_blocks_append_until_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            ctx = multiprocessing.get_context('spawn')
            ready = ctx.Event()
            release = ctx.Event()
            proc = ctx.Process(target=worker, args=(path, ready, release))
            proc.start()
            try:
                self.assertTrue(ready.wait(5), 'lock holder never acquired lock')
                journal = CommandJournal(path)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(journal.append, 1, {'id': 'one'})
                    with self.assertRaises(FutureTimeoutError):
                        future.result(timeout=0.1)
                    release.set()
                    self.assertTrue(future.result(timeout=5))
                self.assertEqual(len(CommandJournal(path).entries()), 1)
            finally:
                release.set()
                proc.join(5)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(5)
            self.assertEqual(proc.exitcode, 0)

    def test_worker_exception_is_propagated(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = CommandJournal(Path(tmp) / 'journal')
            with patch.object(journal, '_append_locked', side_effect=RuntimeError('injected failure')):
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(journal.append, 1, {'id': 'one'})
                    with self.assertRaisesRegex(RuntimeError, 'injected failure'):
                        future.result(timeout=5)


if __name__ == '__main__':
    unittest.main()
