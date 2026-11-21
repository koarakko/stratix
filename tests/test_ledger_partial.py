import unittest
from concurrent.futures import ThreadPoolExecutor
from services.exchange.ledger import Ledger, Posting, LedgerError

class PartialSettlementTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(protected_accounts={'alice'})
        self.ledger.post('fund', (Posting('issuer','BTC',-10), Posting('alice','BTC',10)))
        self.ledger.reserve('r','alice','BTC',8)

    def test_partial_then_release(self):
        self.assertTrue(self.ledger.settle_partial('r','bob',3,'fill-1'))
        self.assertEqual(self.ledger.balance('alice','BTC'),7)
        self.assertEqual(self.ledger.available('alice','BTC'),2)
        self.assertTrue(self.ledger.release('r'))
        self.assertEqual(self.ledger.available('alice','BTC'),7)

    def test_multiple_fills_exactly_once(self):
        self.assertTrue(self.ledger.settle_partial('r','bob',3,'f1'))
        self.assertFalse(self.ledger.settle_partial('r','bob',3,'f1'))
        self.assertTrue(self.ledger.settle_partial('r','bob',5,'f2'))
        self.assertEqual(self.ledger.balance('bob','BTC'),8)
        self.assertEqual(self.ledger.available('alice','BTC'),2)
        with self.assertRaises(LedgerError): self.ledger.release('r')

    def test_conflicting_fill_and_overfill(self):
        self.ledger.settle_partial('r','bob',3,'f1')
        with self.assertRaises(LedgerError): self.ledger.settle_partial('r','bob',4,'f1')
        with self.assertRaises(LedgerError): self.ledger.settle_partial('r','bob',6,'f2')
        self.assertEqual(self.ledger.available('alice','BTC'),2)

    def test_invalid_fill_does_not_consume_id(self):
        with self.assertRaises(LedgerError): self.ledger.settle_partial('r','alice',3,'f1')
        with self.assertRaises(LedgerError): self.ledger.settle_partial('r','bob',True,'f1')
        self.assertTrue(self.ledger.settle_partial('r','bob',3,'f1'))

    def test_full_settle_rejected_after_partial(self):
        self.ledger.settle_partial('r','bob',3,'f1')
        with self.assertRaises(LedgerError): self.ledger.settle('r','bob')

    def test_parallel_fill_deduplication(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:self.ledger.settle_partial('r','bob',3,'f1'),range(20)))
        self.assertEqual(sum(results),1)
        self.assertEqual(self.ledger.balance('bob','BTC'),3)

    def test_transaction_collision_restores_hold(self):
        self.ledger.post('reservation-fill:f1',(Posting('issuer','ETH',-1),Posting('bob','ETH',1)))
        with self.assertRaises(LedgerError): self.ledger.settle_partial('r','bob',3,'f1')
        self.assertEqual(self.ledger.available('alice','BTC'),2)
        self.assertTrue(self.ledger.settle_partial('r','bob',3,'f2'))

if __name__=='__main__': unittest.main()
