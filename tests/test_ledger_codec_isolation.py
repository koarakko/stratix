import json
import unittest
from services.exchange.ledger_journal_codec import encode_ledger_command, decode_ledger_command

class CodecIsolationTests(unittest.TestCase):
    def test_post_input_mutation_does_not_change_encoded_payload(self):
        postings = [dict(account='issuer', asset='BTC', amount=-7), dict(account='alice', asset='BTC', amount=7)]
        payload = encode_ledger_command('post', transaction_id='fund-1', postings=postings)
        postings[0]['amount'] = -999
        postings.append(dict(account='mallory', asset='BTC', amount=999))
        self.assertEqual(payload['command']['postings'], [dict(account='issuer', asset='BTC', amount=-7), dict(account='alice', asset='BTC', amount=7)])
        self.assertEqual(dict(decode_ledger_command(payload)[1])['postings'][0], ('issuer', 'BTC', -7))

    def test_post_encoded_payload_is_json_serializable(self):
        payload = encode_ledger_command('post', transaction_id='fund-2', postings=[dict(account='issuer', asset='BTC', amount=-3), dict(account='alice', asset='BTC', amount=3)])
        self.assertEqual(json.loads(json.dumps(payload)), payload)

    def test_reserve_roundtrip(self):
        payload = encode_ledger_command('reserve', reservation_id='r', account='alice', asset='BTC', amount=2)
        self.assertEqual(dict(decode_ledger_command(payload)[1])['amount'], 2)
