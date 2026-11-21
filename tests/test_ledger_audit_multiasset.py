import unittest
from collections import namedtuple
from services.exchange.ledger_audit import audit_transactions, LedgerAuditError

Posting = namedtuple('Posting', 'account asset amount')

class MultiAssetAuditTests(unittest.TestCase):
    def test_balanced_multiasset_transaction(self):
        tx = {'swap': (Posting('alice', 'BTC', -5), Posting('bob', 'BTC', 5), Posting('bob', 'ETH', -12), Posting('alice', 'ETH', 12))}
        self.assertEqual(audit_transactions(tx), {('alice', 'BTC'):-5, ('bob', 'BTC'):5, ('bob', 'ETH'):-12, ('alice', 'ETH'):12})

    def test_second_asset_imbalance_fails(self):
        tx = {'swap': (Posting('alice', 'BTC', -5), Posting('bob', 'BTC', 5), Posting('bob', 'ETH', -12), Posting('alice', 'ETH', 11))}
        with self.assertRaises(LedgerAuditError): audit_transactions(tx)

    def test_expected_balances_detect_wrong_asset(self):
        tx = {'fund': (Posting('issuer', 'BTC', -5), Posting('alice', 'BTC', 5))}
        with self.assertRaises(LedgerAuditError):
            audit_transactions(tx, {('issuer','BTC'):-5, ('alice','ETH'):5})

    def test_empty_snapshot_rejects_nonzero_expected(self):
        with self.assertRaises(LedgerAuditError): audit_transactions({}, {('alice','BTC'):1})

    def test_expected_mapping_not_mutated(self):
        tx = {'fund': (Posting('issuer', 'BTC', -5), Posting('alice', 'BTC', 5))}
        expected = {('issuer','BTC'):-5, ('alice','BTC'):5, ('unused','BTC'):0}
        audit_transactions(tx, expected)
        self.assertEqual(expected[('unused','BTC')], 0)
