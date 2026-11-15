import tempfile
import unittest
from pathlib import Path
from services.exchange.command_log import CommandJournal, JournalError

class ExternalMutationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'journal'
        self.journal = CommandJournal(self.path)
        self.assertTrue(self.journal.append(1, {'type': 'demo'}))

    def test_missing_file_fails_closed(self):
        self.path.unlink()
        with self.assertRaises(JournalError):
            self.journal.read_all()
        with self.assertRaises(JournalError):
            self.journal.append(2, {'type': 'next'})
        self.assertFalse(self.path.exists())

    def test_empty_replacement_fails_closed(self):
        self.path.write_bytes(b'')
        with self.assertRaises(JournalError):
            self.journal.append(2, {'type': 'next'})
        self.assertEqual(self.path.read_bytes(), b'')

    def test_external_valid_append_fails_closed(self):
        other = CommandJournal(self.path)
        self.assertTrue(other.append(2, {'type': 'external'}))
        with self.assertRaises(JournalError):
            self.journal.append(2, {'type': 'external'})

    def test_unchanged_retry_and_append(self):
        self.assertFalse(self.journal.append(1, {'type': 'demo'}))
        self.assertTrue(self.journal.append(2, {'type': 'next'}))
        self.assertEqual(len(self.journal.read_all()), 2)

if __name__ == '__main__':
    unittest.main()
