import unittest
from services.exchange.ledger_journal_codec import encode_ledger_command
from services.exchange.ledger_replay_plan import LedgerReplayPlanError, plan_ledger_replay

class ReplayIterationFailures(unittest.TestCase):
    def test_runtime_error_during_iteration_fails_closed(self):
        def broken():
            yield {"sequence": 1, "payload": encode_ledger_command("release", reservation_id="r")}
            raise RuntimeError("source failed")
        with self.assertRaisesRegex(LedgerReplayPlanError, "iteration failed"):
            plan_ledger_replay(broken())

    def test_io_error_during_iteration_fails_closed(self):
        def broken():
            yield {"sequence": 1, "payload": encode_ledger_command("release", reservation_id="r")}
            raise OSError("disk read failed")
        with self.assertRaisesRegex(LedgerReplayPlanError, "iteration failed"):
            plan_ledger_replay(broken())

    def test_invalid_command_still_fails_closed(self):
        with self.assertRaises(LedgerReplayPlanError):
            plan_ledger_replay([{"sequence":1,"payload":{"type":"wrong"}}])

    def test_successful_iteration(self):
        plan = plan_ledger_replay([{"sequence":1,"payload":encode_ledger_command("release",reservation_id="r")}])
        self.assertEqual(plan[0].sequence, 1)
