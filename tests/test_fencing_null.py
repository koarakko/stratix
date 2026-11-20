"""Reject absent tokens before and after revocation (local gate only)."""
import unittest
from services.exchange.fencing import FencingError, FencingGate, LeadershipToken


class NullTokenTests(unittest.TestCase):
    def test_no_leader_rejects_none_authorize(self):
        with self.assertRaises(FencingError):
            FencingGate(0).authorize(None)

    def test_no_leader_rejects_none_operation(self):
        called = []
        with self.assertRaises(FencingError):
            FencingGate(0).run_authorized(None, called.append, 'unsafe')
        self.assertEqual(called, [])

    def test_revoked_rejects_none(self):
        gate = FencingGate(0)
        gate.install(LeadershipToken(1, 'a'))
        gate.revoke()
        with self.assertRaises(FencingError):
            gate.authorize(None)

    def test_valid_token_still_authorizes(self):
        gate = FencingGate(0)
        token = LeadershipToken(1, 'a')
        gate.install(token)
        self.assertEqual(gate.run_authorized(token, lambda: 42), 42)
