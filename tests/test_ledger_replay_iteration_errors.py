import unittest
from services.exchange.ledger_replay_plan import plan_ledger_replay, LedgerReplayPlanError
from services.exchange.ledger_journal_codec import encode_ledger_command


class ReplayIterationErrors(unittest.TestCase):
    def test_value_error_from_iterator_fails_closed(self):
        def broken():
            yield {'sequence': 1, 'payload': encode_ledger_command('release', reservation_id='r')}
            raise ValueError('invalid on-disk record')
        with self.assertRaisesRegex(LedgerReplayPlanError, 'iteration failed'):
            plan_ledger_replay(broken())

    def test_type_error_from_iterator_fails_closed(self):
        def broken():
            yield {'sequence': 1, 'payload': encode_ledger_command('release', reservation_id='r')}
            raise TypeError('decoder failed')
        with self.assertRaisesRegex(LedgerReplayPlanError, 'iteration failed'):
            plan_ledger_replay(broken())

    def test_valid_iteration(self):
        entry = {'sequence': 1, 'payload': encode_ledger_command('release', reservation_id='r')}
        self.assertEqual(len(plan_ledger_replay(iter([entry]))), 1)
