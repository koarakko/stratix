import unittest
from services.exchange.fencing import FencingError, FencingGate, LeadershipToken


class FencingGateTests(unittest.TestCase):
    def test_no_leader_denies(self):
        with self.assertRaises(FencingError):
            FencingGate(0).authorize(LeadershipToken(1, "a"))

    def test_new_epoch_revokes_old_leader(self):
        gate = FencingGate(0)
        first = LeadershipToken(1, "a")
        second = LeadershipToken(2, "b")
        gate.install(first)
        gate.authorize(first)
        gate.install(second)
        gate.authorize(second)
        with self.assertRaises(FencingError):
            gate.authorize(first)

    def test_same_epoch_conflict_rejected(self):
        gate = FencingGate(0)
        gate.install(LeadershipToken(1, "a"))
        with self.assertRaises(FencingError):
            gate.install(LeadershipToken(1, "b"))

    def test_replay_and_restart_high_water_mark(self):
        gate = FencingGate(8)
        with self.assertRaises(FencingError):
            gate.install(LeadershipToken(8, "a"))
        gate.install(LeadershipToken(9, "a"))
        restarted = FencingGate(9)
        with self.assertRaises(FencingError):
            restarted.install(LeadershipToken(9, "a"))
        restarted.install(LeadershipToken(10, "b"))

    def test_revocation_denies(self):
        gate = FencingGate(0)
        token = LeadershipToken(1, "a")
        gate.install(token)
        gate.revoke()
        with self.assertRaises(FencingError):
            gate.authorize(token)

    def test_invalid_epochs_and_holders(self):
        for epoch in (True, 0, -1, 1.5):
            with self.subTest(epoch=epoch), self.assertRaises(FencingError):
                LeadershipToken(epoch, "a")
        with self.assertRaises(FencingError):
            LeadershipToken(1, " ")
        with self.assertRaises(FencingError):
            FencingGate(True)


if __name__ == "__main__":
    unittest.main()
