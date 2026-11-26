import unittest
from itertools import repeat
from types import SimpleNamespace

from services.replication.log_snapshot import (
    DEFAULT_MAX_LOG_SNAPSHOT_ENTRIES,
    DEFAULT_MAX_LOG_SNAPSHOT_PAYLOAD_BYTES,
    LogSnapshotLimitError,
    materialize_log_snapshot,
)


class LogSnapshotTests(unittest.TestCase):
    def test_exact_entry_limit_is_accepted(self):
        self.assertEqual(materialize_log_snapshot(iter((1, 2, 3)), max_entries=3), (1, 2, 3))

    def test_empty_snapshot_accepts_zero_limits(self):
        self.assertEqual(materialize_log_snapshot((), max_entries=0, max_payload_bytes=0), ())

    def test_zero_entry_limit_rejects_nonempty_snapshot(self):
        with self.assertRaises(LogSnapshotLimitError):
            materialize_log_snapshot((1,), max_entries=0)

    def test_over_entry_limit_fails_after_one_lookahead(self):
        consumed = []
        def entries():
            for value in range(100):
                consumed.append(value)
                yield value
        with self.assertRaises(LogSnapshotLimitError):
            materialize_log_snapshot(entries(), max_entries=3)
        self.assertEqual(consumed, [0, 1, 2, 3])

    def test_exact_payload_byte_limit_is_accepted(self):
        entries = (SimpleNamespace(payload=b'ab'), SimpleNamespace(payload=b'c'))
        self.assertEqual(materialize_log_snapshot(entries, max_payload_bytes=3), entries)

    def test_payload_byte_overflow_fails_before_appending_oversized_entry(self):
        consumed = []
        def entries():
            for payload in (b'ab', b'cd', b'e'):
                consumed.append(payload)
                yield SimpleNamespace(payload=payload)
        with self.assertRaises(LogSnapshotLimitError):
            materialize_log_snapshot(entries(), max_entries=10, max_payload_bytes=3)
        self.assertEqual(consumed, [b'ab', b'cd'])

    def test_default_limits_are_explicit(self):
        self.assertEqual(DEFAULT_MAX_LOG_SNAPSHOT_ENTRIES, 100_000)
        self.assertEqual(DEFAULT_MAX_LOG_SNAPSHOT_PAYLOAD_BYTES, 64 * 1024 * 1024)

    def test_default_entry_limit_rejects_an_unbounded_stream(self):
        with self.assertRaises(LogSnapshotLimitError):
            materialize_log_snapshot(repeat(SimpleNamespace(payload=b'')))

    def test_invalid_limits_rejected(self):
        for value in (True, 1.0, -1, None, "3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                materialize_log_snapshot((), max_entries=value)
            with self.subTest(payload_limit=value), self.assertRaises(ValueError):
                materialize_log_snapshot((), max_payload_bytes=value)

    def test_iterator_creation_failure_propagates(self):
        class BrokenIterable:
            def __iter__(self):
                raise LookupError("iterator init")
        with self.assertRaises(LookupError):
            materialize_log_snapshot(BrokenIterable(), max_entries=1)

    def test_process_control_exception_propagates_on_lookahead(self):
        def interrupted():
            yield 1
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            materialize_log_snapshot(interrupted(), max_entries=1)


if __name__ == "__main__":
    unittest.main()
