import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError


class JournalPayloadAliasingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "commands.journal"

    def test_mutating_original_nested_payload_cannot_change_committed_history(self):
        journal = CommandJournal(self.path)
        payload = {"order": {"amounts": ["1", "2"]}}
        self.assertTrue(journal.append(1, payload))
        original = self.path.read_bytes()
        payload["order"]["amounts"][0] = "999"
        payload["order"]["extra"] = True
        self.assertEqual(journal.entries(), CommandJournal(self.path).entries())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse(journal.append(1, {"order": {"amounts": ["1", "2"]}}))
        with self.assertRaises(JournalError):
            journal.append(1, payload)
        self.assertTrue(journal.append(2, {"kind": "cancel"}))

    def test_mutating_returned_entries_cannot_change_internal_history(self):
        journal = CommandJournal(self.path)
        self.assertTrue(journal.append(1, {"nested": {"values": [1]}}))
        snapshot = journal.entries()
        snapshot[0]["payload"]["nested"]["values"].append(2)
        self.assertEqual(journal.entries(), CommandJournal(self.path).entries())
        self.assertFalse(journal.append(1, {"nested": {"values": [1]}}))
