"""Deterministic local concurrency checks; not a distributed fencing proof."""
import threading
import unittest
from services.exchange.fencing import FencingError, FencingGate, LeadershipToken


class FencingThreadingTests(unittest.TestCase):
    def setUp(self):
        self.gate = FencingGate(0)
        self.old = LeadershipToken(1, 'old')
        self.new = LeadershipToken(2, 'new')
        self.gate.install(self.old)

    def _run_blocked_operation(self, operation):
        entered = threading.Event()
        release = threading.Event()
        done = threading.Event()
        errors = []
        def callback():
            entered.set()
            if not release.wait(3):
                raise TimeoutError('callback not released')
        def worker():
            try:
                self.gate.run_authorized(self.old, callback)
            except BaseException as exc:
                errors.append(exc)
            finally:
                done.set()
        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(entered.wait(3))
        action_started = threading.Event()
        action_done = threading.Event()
        def action():
            action_started.set()
            try:
                operation()
            except BaseException as exc:
                errors.append(exc)
            finally:
                action_done.set()
        changer = threading.Thread(target=action)
        changer.start()
        try:
            self.assertTrue(action_started.wait(3))
            self.assertFalse(action_done.wait(0.05), 'leadership changed during callback')
        finally:
            release.set()
            thread.join(3)
            changer.join(3)
        self.assertFalse(thread.is_alive())
        self.assertFalse(changer.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(done.is_set())
        self.assertTrue(action_done.is_set())

    def test_install_waits_for_inflight_operation(self):
        self._run_blocked_operation(lambda: self.gate.install(self.new))
        self.gate.authorize(self.new)
        with self.assertRaises(FencingError):
            self.gate.authorize(self.old)

    def test_revoke_waits_for_inflight_operation(self):
        self._run_blocked_operation(self.gate.revoke)
        with self.assertRaises(FencingError):
            self.gate.authorize(self.old)

    def test_stale_callback_never_runs_after_leader_change(self):
        self.gate.install(self.new)
        called = []
        with self.assertRaises(FencingError):
            self.gate.run_authorized(self.old, lambda: called.append(True))
        self.assertEqual(called, [])

    def test_operation_failure_does_not_block_later_install(self):
        def fail():
            raise RuntimeError('injected')
        with self.assertRaises(RuntimeError):
            self.gate.run_authorized(self.old, fail)
        self.gate.install(self.new)
        self.gate.authorize(self.new)


if __name__ == '__main__':
    unittest.main()
