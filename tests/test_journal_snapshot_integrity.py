import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError


class JournalSnapshotIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "orders.journal"

    def test_entries_reflect_verified_commits(self):
        journal = CommandJournal(self.path)
        journal.append(1, {"order_id": "a"})
        self.assertEqual(journal.entries(), ({"sequence": 1, "payload": {"order_id": "a"}},))
        self.assertEqual(journal.entries(), journal.read_all())

    def test_entries_reject_external_append(self):
        journal = CommandJournal(self.path)
        journal.append(1, {"order_id": "a"})
        CommandJournal(self.path).append(2, {"order_id": "b"})
        with self.assertRaisesRegex(JournalError, "changed"):
            journal.entries()

    def test_entries_reject_missing_file(self):
        journal = CommandJournal(self.path)
        journal.append(1, {"order_id": "a"})
        self.path.unlink()
        with self.assertRaisesRegex(JournalError, "missing"):
            journal.entries()

    def test_entries_reject_truncated_tail(self):
        journal = CommandJournal(self.path)
        journal.append(1, {"order_id": "a"})
        self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaisesRegex(JournalError, "incomplete"):
            journal.entries()

    def test_entries_reject_checksum_corruption(self):
        journal = CommandJournal(self.path)
        journal.append(1, {"order_id": "a"})
        self.path.write_bytes(self.path.read_bytes().replace(b'"order_id":"a"', b'"order_id":"b"'))
        with self.assertRaises(JournalError):
            journal.entries()


if __name__ == "__main__":
    unittest.main()
