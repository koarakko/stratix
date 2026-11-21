import unittest
from services.exchange.ledger_journal_codec import (
    LedgerCommandError, decode_ledger_command, encode_ledger_command,
)


class LedgerJournalCodecTests(unittest.TestCase):
    def test_round_trip_all_operations(self):
        for op, fields in (
            ('reserve', dict(reservation_id='r', account='alice', asset='BTC', amount=5)),
            ('release', dict(reservation_id='r')),
            ('settle', dict(reservation_id='r', destination='bob')),
            ('settle_partial', dict(reservation_id='r', destination='bob', amount=2, fill_id='f')),
        ):
            with self.subTest(op=op):
                payload = encode_ledger_command(op, **fields)
                self.assertEqual(decode_ledger_command(payload), (op, tuple(sorted(fields.items()))))

    def test_rejects_unknown_version_and_type(self):
        for change in ({'version': 2}, {'version': True}, {'type': 'order'}):
            with self.subTest(change=change), self.assertRaises(LedgerCommandError):
                decode_ledger_command({**encode_ledger_command('release', reservation_id='r'), **change})

    def test_rejects_extra_and_missing_fields(self):
        for fields in ({'reservation_id': 'r', 'extra': 1}, {}):
            with self.subTest(fields=fields), self.assertRaises(LedgerCommandError):
                encode_ledger_command('release', **fields)

    def test_rejects_bool_float_and_negative_amount(self):
        for amount in (True, 1.0, 0, -1):
            with self.subTest(amount=amount), self.assertRaises(LedgerCommandError):
                encode_ledger_command('reserve', reservation_id='r', account='alice', asset='BTC', amount=amount)

    def test_rejects_invalid_identifiers(self):
        for identifier in ('', ' ', None, 123):
            with self.subTest(identifier=identifier), self.assertRaises(LedgerCommandError):
                encode_ledger_command('release', reservation_id=identifier)

    def test_rejects_unknown_operation(self):
        with self.assertRaises(LedgerCommandError):
            encode_ledger_command('post', transaction_id='t')

    def test_cannot_mutate_decoded_command_via_payload(self):
        payload = encode_ledger_command('release', reservation_id='r')
        decoded = decode_ledger_command(payload)
        payload['command']['reservation_id'] = 'changed'
        self.assertEqual(decoded, ('release', (('reservation_id', 'r'),)))


if __name__ == '__main__':
    unittest.main()
