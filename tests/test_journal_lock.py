import multiprocessing
import tempfile
import unittest
from pathlib import Path
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
            ready = multiprocessing.Event()
            release = multiprocessing.Event()
            proc = multiprocessing.Process(target=worker, args=(path, ready, release))
            proc.start()
            try:
                self.assertTrue(ready.wait(5))
                import threading
                journal = CommandJournal(path)
                done = threading.Event()
                thread = threading.Thread(target=lambda: (journal.append(1, {'id':'one'}), done.set()))
                thread.start()
                self.assertFalse(done.wait(0.1))
                release.set()
                self.assertTrue(done.wait(5))
                thread.join(5)
                self.assertEqual(len(CommandJournal(path).entries()), 1)
            finally:
                release.set()
                proc.join(5)
                if proc.is_alive(): proc.terminate(); proc.join()

if __name__ == '__main__': unittest.main()
