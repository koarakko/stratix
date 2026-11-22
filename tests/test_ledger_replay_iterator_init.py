import unittest
from services.exchange.ledger_replay_plan import plan_ledger_replay, LedgerReplayPlanError


class BrokenIterable:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


class IteratorInitializationTests(unittest.TestCase):
    def test_oserror_is_wrapped(self):
        with self.assertRaises(LedgerReplayPlanError) as caught:
            plan_ledger_replay(BrokenIterable(OSError("disk error")))
        self.assertIsInstance(caught.exception.__cause__, OSError)

    def test_runtimeerror_is_wrapped(self):
        with self.assertRaises(LedgerReplayPlanError):
            plan_ledger_replay(BrokenIterable(RuntimeError("snapshot invalid")))

    def test_valueerror_is_wrapped(self):
        with self.assertRaises(LedgerReplayPlanError):
            plan_ledger_replay(BrokenIterable(ValueError("snapshot invalid")))

    def test_empty_snapshot_is_valid(self):
        self.assertEqual(plan_ledger_replay(iter(())), ())

    def test_valid_command(self):
        entries = [{"sequence": 1, "payload": {"type": "ledger", "version": 1,
                   "command": {"operation": "release", "reservation_id": "r"}}}]
        self.assertEqual(plan_ledger_replay(entries)[0].operation, "release")
