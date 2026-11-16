"""Independent-process contention regression for the local journal (POSIX)."""
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError


def _contend(path, ready, start, results, identifier, payload_id):
    try:
        journal = CommandJournal(path)
        ready.put(identifier)
        if not start.wait(10):
            results.put((identifier, 'timeout'))
            return
        try:
            outcome = journal.append(1, {'id': payload_id})
            results.put((identifier, 'committed' if outcome else 'retry'))
        except JournalError:
            results.put((identifier, 'rejected'))
    except Exception as exc:
        results.put((identifier, f'error:{type(exc).__name__}:{exc}'))


class JournalProcessRaceTests(unittest.TestCase):
    def _race(self, payloads):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            ctx = multiprocessing.get_context('spawn')
            ready, results, start = ctx.Queue(), ctx.Queue(), ctx.Event()
            workers = [ctx.Process(target=_contend, args=(path, ready, start, results, name, payload))
                       for name, payload in payloads.items()]
            for process in workers:
                process.start()
            try:
                self.assertEqual({ready.get(timeout=10) for _ in workers}, set(payloads))
                start.set()
                observed = dict(results.get(timeout=10) for _ in workers)
            finally:
                start.set()
                for process in workers:
                    process.join(5)
                    if process.is_alive():
                        process.terminate()
                        process.join(5)
            self.assertTrue(all(process.exitcode == 0 for process in workers))
            self.assertEqual(set(observed), set(payloads))
            entries = CommandJournal(path).entries()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['sequence'], 1)
            winner = entries[0]['payload']['id']
            self.assertFalse(CommandJournal(path).append(1, {'id': winner}))
            with self.assertRaisesRegex(JournalError, 'conflicting committed sequence'):
                CommandJournal(path).append(1, {'id': 'different'})
            self.assertEqual(len(CommandJournal(path).entries()), 1)
            return observed, winner

    def test_two_processes_one_sequence_one_commit(self):
        # Both instances open the absent journal before the start barrier.
        observed, winner = self._race({'first': 'first', 'second': 'second'})
        self.assertEqual(sorted(observed.values()), ['committed', 'rejected'])
        self.assertEqual(winner, next(name for name, status in observed.items()
                                      if status == 'committed'))

    def test_two_processes_identical_retry(self):
        observed, winner = self._race({'first': 'same', 'second': 'same'})
        self.assertEqual(sorted(observed.values()), ['committed', 'rejected'])
        self.assertEqual(winner, 'same')


if __name__ == '__main__':
    unittest.main()
