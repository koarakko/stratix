import unittest
from services.exchange.fencing import FencingError, FencingGate, LeadershipToken


class FencingReentrancyTests(unittest.TestCase):
    def setUp(self):
        self.gate = FencingGate(0)
        self.old = LeadershipToken(1, 'old')
        self.new = LeadershipToken(2, 'new')
        self.gate.install(self.old)

    def test_reentrant_install_is_rejected_without_consuming_epoch(self):
        with self.assertRaises(FencingError):
            self.gate.run_authorized(self.old, self.gate.install, self.new)
        self.gate.authorize(self.old)
        self.gate.install(self.new)
        self.gate.authorize(self.new)

    def test_reentrant_revoke_is_rejected(self):
        with self.assertRaises(FencingError):
            self.gate.run_authorized(self.old, self.gate.revoke)
        self.gate.authorize(self.old)

    def test_nested_authorized_operation_is_rejected(self):
        with self.assertRaises(FencingError):
            self.gate.run_authorized(self.old, self.gate.run_authorized, self.old, lambda: None)
        self.assertEqual(self.gate.run_authorized(self.old, lambda: 42), 42)

    def test_exception_releases_operation_guard(self):
        def fail():
            raise RuntimeError('failure')
        with self.assertRaises(RuntimeError):
            self.gate.run_authorized(self.old, fail)
        self.gate.revoke()
        with self.assertRaises(FencingError):
            self.gate.authorize(self.old)

    def test_normal_operation_returns_value(self):
        self.assertEqual(self.gate.run_authorized(self.old, lambda x: x + 1, 2), 3)
