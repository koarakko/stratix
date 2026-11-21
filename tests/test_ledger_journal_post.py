import unittest
from services.exchange.ledger_journal_codec import LedgerCommandError, encode_ledger_command, decode_ledger_command

class LedgerJournalPostTests(unittest.TestCase):
    def test_roundtrip_funding(self):
        postings = [dict(account='issuer', asset='BTC', amount=-10), dict(account='alice', asset='BTC', amount=10)]
        payload = encode_ledger_command('post', transaction_id='fund-1', postings=postings)
        expected = ('post', (('postings', (('issuer', 'BTC', -10), ('alice', 'BTC', 10))), ('transaction_id', 'fund-1')))
        self.assertEqual(decode_ledger_command(payload), expected)
        postings[0]['amount'] = -100
        self.assertEqual(decode_ledger_command(encode_ledger_command('post', transaction_id='fund-1', postings=[dict(account='issuer', asset='BTC', amount=-10), dict(account='alice', asset='BTC', amount=10)])), expected)

    def test_rejects_bad_postings(self):
        good = [dict(account='issuer', asset='BTC', amount=-10), dict(account='alice', asset='BTC', amount=10)]
        cases = [[], [good[0]], [good[0], dict(account='alice', asset='ETH', amount=10)],
                 [good[0], dict(account='alice', asset='BTC', amount=True)],
                 [good[0], dict(account='alice', asset='BTC', amount=10, extra='x')],
                 [good[0], dict(account=' ', asset='BTC', amount=10)],
                 [good[0], dict(account='alice', asset='BTC', amount=10.0)]]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(LedgerCommandError):
                encode_ledger_command('post', transaction_id='fund-1', postings=case)

    def test_rejects_reserved_transaction_ids(self):
        for txid in ('reservation-settle:r', 'reservation-fill:f'):
            with self.subTest(txid=txid), self.assertRaises(LedgerCommandError):
                encode_ledger_command('post', transaction_id=txid, postings=[dict(account='a', asset='BTC', amount=-1), dict(account='b', asset='BTC', amount=1)])

    def test_rejects_missing_extra_or_invalid_id(self):
        postings = [dict(account='a', asset='BTC', amount=-1), dict(account='b', asset='BTC', amount=1)]
        for fields in (dict(postings=postings), dict(transaction_id=' ', postings=postings), dict(transaction_id='t', postings=postings, unexpected=1)):
            with self.subTest(fields=fields), self.assertRaises(LedgerCommandError):
                encode_ledger_command('post', **fields)
