import threading
import unittest
from services.exchange.fencing import FencingError, FencingGate, LeadershipToken


class FencingOperationTests(unittest.TestCase):
    def test_authorized_operation_returns_result_once(self):
        gate = FencingGate(0)
        token = LeadershipToken(1, 'a')
        gate.install(token)
        calls = []
        self.assertEqual(gate.run_authorized(token, lambda x: calls.append(x) or x * 2, 4), 8)
        self.assertEqual(calls, [4])

    def test_stale_operation_not_invoked(self):
        gate = FencingGate(0)
        old = LeadershipToken(1, 'a')
        gate.install(old)
        gate.install(LeadershipToken(2, 'b'))
        called = []
        with self.assertRaises(FencingError):
            gate.run_authorized(old, called.append, 'unsafe')
        self.assertEqual(called, [])

    def test_revoked_operation_not_invoked(self):
        gate = FencingGate(0)
        token = LeadershipToken(1, 'a')
        gate.install(token)
        gate.revoke()
        with self.assertRaises(FencingError):
            gate.run_authorized(token, lambda: self.fail('must not run'))

    def test_operation_failure_does_not_change_leadership(self):
        gate = FencingGate(0)
        token = LeadershipToken(1, 'a')
        gate.install(token)
        def fail():
            raise RuntimeError('write failed')
        with self.assertRaises(RuntimeError):
            gate.run_authorized(token, fail)
        gate.authorize(token)

    def test_leadership_change_waits_for_local_operation(self):
        gate = FencingGate(0)
        old = LeadershipToken(1, 'a')
        new = LeadershipToken(2, 'b')
        gate.install(old)
        entered = threading.Event()
        release = threading.Event()
        changed = threading.Event()
        def operation():
            entered.set()
            if not release.wait(3):
                raise AssertionError('operation timeout')
        worker = threading.Thread(target=lambda: gate.run_authorized(old, operation))
        worker.start()
        self.assertTrue(entered.wait(3))
        changer = threading.Thread(target=lambda: (gate.install(new), changed.set()))
        changer.start()
        try:
            self.assertFalse(changed.wait(0.05))
        finally:
            release.set()
            worker.join(3)
            changer.join(3)
        self.assertFalse(worker.is_alive())
        self.assertFalse(changer.is_alive())
        self.assertTrue(changed.is_set())
        with self.assertRaises(FencingError):
            gate.authorize(old)
        gate.authorize(new)


if __name__ == '__main__':
    unittest.main()
