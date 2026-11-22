import unittest
from services.exchange.ledger_journal_codec import encode_ledger_command
from services.exchange.ledger_replay_plan import plan_ledger_replay, LedgerReplayPlanError

def entry(n, operation='release', **kwargs):
    return {'sequence': n, 'payload': encode_ledger_command(operation, **(kwargs or {'reservation_id': 'r'}))}

class ReplayPlanTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(plan_ledger_replay([]), ())

    def test_multiple_operations_and_immutable_result(self):
        items = [entry(1, 'post', transaction_id='fund', postings=[{'account':'bank','asset':'BTC','amount':-10},{'account':'alice','asset':'BTC','amount':10}]), entry(2,'reserve',reservation_id='r',account='alice',asset='BTC',amount=7), entry(3,'settle_partial',reservation_id='r',destination='bob',amount=3,fill_id='f'), entry(4)]
        result = plan_ledger_replay(items)
        self.assertEqual([c.operation for c in result], ['post','reserve','settle_partial','release'])
        items[0]['payload']['command']['postings'][0]['amount'] = -999
        self.assertEqual(dict(result[0].arguments)['postings'][0], ('bank','BTC',-10))
        with self.assertRaises(AttributeError): result[0].operation = 'settle'

    def test_gap(self):
        with self.assertRaises(LedgerReplayPlanError): plan_ledger_replay([entry(2)])

    def test_duplicate(self):
        with self.assertRaises(LedgerReplayPlanError): plan_ledger_replay([entry(1),entry(1)])

    def test_boolean_sequence(self):
        with self.assertRaises(LedgerReplayPlanError): plan_ledger_replay([{'sequence':True,'payload':entry(1)['payload']}])

    def test_bad_envelope(self):
        with self.assertRaises(LedgerReplayPlanError): plan_ledger_replay([{'sequence':1,'payload':{'type':'ledger'}}])

    def test_invalid_later_entry_rejects_whole_plan(self):
        with self.assertRaises(LedgerReplayPlanError): plan_ledger_replay([entry(1), {'sequence':2,'payload':{'type':'other'}}])

    def test_unexpected_fields(self):
        with self.assertRaises(LedgerReplayPlanError): plan_ledger_replay([{'sequence':1,'payload':entry(1)['payload'],'extra':1}])

    def test_non_iterable(self):
        with self.assertRaises(LedgerReplayPlanError): plan_ledger_replay(None)

    def test_unsupported_operation(self):
        with self.assertRaises(LedgerReplayPlanError): plan_ledger_replay([{'sequence':1,'payload':{'type':'ledger','version':1,'command':{'operation':'withdraw'}}}])

if __name__ == '__main__': unittest.main()
