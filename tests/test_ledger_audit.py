import unittest
from collections import namedtuple
from services.exchange.ledger_audit import audit_transactions, LedgerAuditError

Posting = namedtuple('Posting', 'account asset amount')

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tx = {'fund': (Posting('issuer','BTC',-10), Posting('alice','BTC',10))}

    def test_balances(self):
        self.assertEqual(audit_transactions(self.tx), {('issuer','BTC'):-10,('alice','BTC'):10})
    def test_expected_balances(self):
        self.assertEqual(audit_transactions(self.tx, {('issuer','BTC'):-10,('alice','BTC'):10}), audit_transactions(self.tx))
    def test_expected_zero_normalization(self):
        self.assertEqual(audit_transactions({}, {('alice','BTC'):0}), {})
    def test_balance_mismatch(self):
        with self.assertRaises(LedgerAuditError): audit_transactions(self.tx, {('alice','BTC'):9})
    def test_unbalanced(self):
        with self.assertRaises(LedgerAuditError): audit_transactions({'x': (Posting('a','BTC',-3),Posting('b','BTC',2))})
    def test_cross_asset_offset(self):
        with self.assertRaises(LedgerAuditError): audit_transactions({'x': (Posting('a','BTC',-3),Posting('b','ETH',3))})
    def test_invalid_id(self):
        with self.assertRaises(LedgerAuditError): audit_transactions({' ':self.tx['fund']})
    def test_invalid_posting(self):
        with self.assertRaises(LedgerAuditError): audit_transactions({'x': (Posting('a','BTC',True), Posting('b','BTC',-1))})
    def test_short_transaction(self):
        with self.assertRaises(LedgerAuditError): audit_transactions({'x': (Posting('a','BTC',1),)})
    def test_invalid_expected(self):
        with self.assertRaises(LedgerAuditError): audit_transactions(self.tx, {('a','BTC'):True})
    def test_cancellation_to_zero(self):
        tx = dict(self.tx)
        tx['reverse'] = (Posting('alice','BTC',-10), Posting('issuer','BTC',10))
        self.assertEqual(audit_transactions(tx), {})
    def test_input_unchanged(self):
        snapshot = dict(self.tx)
        audit_transactions(self.tx)
        self.assertEqual(snapshot, self.tx)

if __name__ == '__main__': unittest.main()
