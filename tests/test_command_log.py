import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


class CommandJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'orders.journal'

    def test_roundtrip_reopen_and_identical_retry(self):
        log = CommandJournal(self.path)
        self.assertTrue(log.append(1, {'type': 'place', 'quantity': '1.25'}))
        self.assertFalse(log.append(1, {'type': 'place', 'quantity': '1.25'}))
        self.assertTrue(log.append(2, {'type': 'cancel', 'order_id': 'a'}))
        self.assertEqual(CommandJournal(self.path).entries(), log.entries())
        self.assertEqual(len(self.path.read_bytes().splitlines()), 2)

    def test_reject_conflict_gap_and_invalid_payload_without_mutation(self):
        log = CommandJournal(self.path)
        log.append(1, {'x': 1})
        before = self.path.read_bytes()
        for seq, payload in ((1, {'x': 2}), (3, {'x': 3}), (True, {'x': 4}), (2, {'x': float('nan')}), (2, {'x': object()})):
            with self.subTest(seq=seq, payload=str(payload)), self.assertRaises(JournalError):
                log.append(seq, payload)
        self.assertEqual(self.path.read_bytes(), before)

    def test_truncated_tail_fails_closed_without_repair(self):
        log = CommandJournal(self.path)
        log.append(1, {'x': 1})
        self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaisesRegex(JournalError, 'incomplete'):
            CommandJournal(self.path)

    def test_checksum_tamper_and_reordered_sequence_rejected(self):
        log = CommandJournal(self.path)
        log.append(1, {'x': 1})
        log.append(2, {'x': 2})
        original = self.path.read_bytes()
        self.path.write_bytes(original.replace(b'"x":1', b'"x":9'))
        with self.assertRaises(JournalError):
            CommandJournal(self.path)
        self.path.write_bytes(original.splitlines(keepends=True)[1] + original.splitlines(keepends=True)[0])
        with self.assertRaises(JournalError):
            CommandJournal(self.path)

    def test_io_failure_poison_prevents_retry(self):
        log = CommandJournal(self.path)
        with patch('services.exchange.command_log.os.write', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                log.append(1, {'x': 1})
        with self.assertRaisesRegex(JournalError, 'poisoned'):
            log.append(1, {'x': 1})
        self.assertEqual(CommandJournal(self.path).entries(), ())

    def test_empty_file_and_invalid_envelope(self):
        self.path.write_bytes(b'')
        self.assertEqual(CommandJournal(self.path).entries(), ())
        self.path.write_bytes(json.dumps({'data': {'sequence': 1, 'payload': {}}, 'sha256': 'wrong'}).encode() + b'\n')
        with self.assertRaises(JournalError):
            CommandJournal(self.path)


if __name__ == '__main__':
    unittest.main()
