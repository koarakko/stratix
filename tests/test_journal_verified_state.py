import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError, _record


class JournalVerifiedStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "orders.journal"
        self.journal = CommandJournal(self.path)
        self.assertTrue(self.journal.append(1, {"order": "a"}))

    def _state(self):
        j = self.journal
        return (j._observed_file, j._file_identity, j._verified_size, j._entries)

    def test_corrupt_record_does_not_advance_verified_state(self):
        previous = self._state()
        original = self.path.read_bytes()
        self.path.write_bytes(original.replace(b'"order":"a"', b'"order":"b"'))
        with self.assertRaises(JournalError):
            self.journal.entries()
        self.assertEqual(self._state(), previous)
        with self.assertRaises(JournalError):
            self.journal.append(2, {"order": "next"})
        self.assertEqual(self._state(), previous)
        self.path.write_bytes(original)
        self.assertEqual(self.journal.entries(), previous[3])
        self.assertFalse(self.journal.append(1, {"order": "a"}))
        self.assertTrue(self.journal.append(2, {"order": "next"}))

    def test_valid_external_append_does_not_advance_verified_state(self):
        previous = self._state()
        self.path.write_bytes(self.path.read_bytes() + _record(2, {"order": "external"}))
        with self.assertRaisesRegex(JournalError, "changed"):
            self.journal.entries()
        self.assertEqual(self._state(), previous)
        with self.assertRaises(JournalError):
            self.journal.append(2, {"order": "external"})
        self.assertEqual(self._state(), previous)

    def test_initial_corrupt_file_does_not_become_verified(self):
        other = self.path.with_name("corrupt.journal")
        other.write_bytes(b'not-json\n')
        with self.assertRaises(JournalError):
            CommandJournal(other)


if __name__ == "__main__":
    unittest.main()
