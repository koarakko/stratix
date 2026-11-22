import unittest
from services.exchange.ledger_journal_codec import encode_ledger_command
from services.exchange.ledger_replay_plan import LedgerReplayPlanError, plan_ledger_replay


def entry(n):
    return {"sequence": n, "payload": encode_ledger_command("release", reservation_id="r")}


class ReplayLimitsTests(unittest.TestCase):
    def test_exact_limit(self):
        self.assertEqual(len(plan_ledger_replay([entry(1), entry(2)], max_commands=2)), 2)

    def test_over_limit_rejected(self):
        with self.assertRaisesRegex(LedgerReplayPlanError, "exceeds max_commands"):
            plan_ledger_replay([entry(1), entry(2)], max_commands=1)

    def test_generator_over_limit(self):
        with self.assertRaises(LedgerReplayPlanError):
            plan_ledger_replay((entry(i) for i in range(1, 10)), max_commands=3)

    def test_invalid_limit_rejected(self):
        for value in (0, -1, True, 1.0, "2", None):
            with self.subTest(value=value), self.assertRaises(LedgerReplayPlanError):
                plan_ledger_replay([], max_commands=value)

    def test_empty_snapshot(self):
        self.assertEqual(plan_ledger_replay([], max_commands=1), ())

    def test_no_partial_plan_returned(self):
        consumed = []
        def source():
            for i in range(1, 5):
                consumed.append(i)
                yield entry(i)
        with self.assertRaises(LedgerReplayPlanError):
            plan_ledger_replay(source(), max_commands=2)
        self.assertEqual(consumed, [1, 2, 3])

if __name__ == "__main__":
    unittest.main()
