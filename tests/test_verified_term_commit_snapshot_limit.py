import unittest
from dataclasses import replace

from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.term_log import append_term
from services.replication.verified_term_commit import verified_term_commit_index


class VerifiedTermSnapshotLimitTests(unittest.TestCase):
    def setUp(self):
        self.entries = append_term(append_term(append_term((), 2, b'a'), 3, b'b'), 3, b'c')
        self.reports = {
            'leader': (3, 3, self.entries[2].entry_hash, True),
            'f1': (3, 2, self.entries[1].entry_hash, True),
            'f2': (3, 0, None, True),
        }

    def call(self, entries=None, **changes):
        args = dict(term=3, previous=0, entries=self.entries if entries is None else entries,
                    leader_id='leader', max_entries=3)
        args.update(changes)
        return verified_term_commit_index(('leader', 'f1', 'f2'), self.reports, **args)

    def test_exact_limit_accepts_verified_commit(self):
        self.assertEqual(self.call(), 2)

    def test_oversized_snapshot_fails_closed(self):
        with self.assertRaises(QuorumWatermarkError):
            self.call(max_entries=2)

    def test_invalid_limit_fails_closed(self):
        for value in (True, -1, 1.5, None):
            with self.subTest(value=value), self.assertRaises(QuorumWatermarkError):
                self.call(max_entries=value)
            with self.subTest(payload_limit=value), self.assertRaises(QuorumWatermarkError):
                self.call(max_payload_bytes=value)

    def test_infinite_stream_is_bounded_and_rejected(self):
        consumed = []
        def endless():
            for entry in self.entries:
                consumed.append(entry.sequence)
                yield entry
            while True:
                consumed.append(len(consumed) + 1)
                yield self.entries[-1]
        with self.assertRaises(QuorumWatermarkError):
            self.call(entries=endless(), max_entries=2)
        self.assertEqual(consumed, [1, 2, 3])

    def test_payload_byte_limit_fails_closed(self):
        with self.assertRaises(QuorumWatermarkError):
            self.call(max_payload_bytes=2)

    def test_exact_payload_byte_limit_accepts_snapshot(self):
        self.assertEqual(self.call(max_payload_bytes=3), 2)

    def test_failure_does_not_poison_fresh_retry(self):
        with self.assertRaises(QuorumWatermarkError):
            self.call(max_entries=2)
        self.assertEqual(self.call(), 2)

    def test_process_control_exception_on_limit_lookahead_propagates(self):
        def interrupted():
            yield from self.entries[:2]
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.call(entries=interrupted(), max_entries=2)


    def test_v2_commit_rejects_bytes_subclass_even_when_byte_cap_allows_it(self):
        class LyingBytes(bytes):
            def __len__(self):
                return 0
        altered = (replace(self.entries[0], payload=LyingBytes(b'a')),) + self.entries[1:]
        with self.assertRaises(QuorumWatermarkError):
            self.call(entries=altered, max_payload_bytes=100)


    def test_v2_commit_rejects_hash_subclass_with_overridden_comparison(self):
        class LyingHash(str):
            def __eq__(self, other):
                return True
            def __ne__(self, other):
                return False
            __hash__ = str.__hash__
        altered = (replace(self.entries[0], previous_hash=LyingHash("0" * 64)),) + self.entries[1:]
        with self.assertRaises(QuorumWatermarkError):
            self.call(entries=altered, max_payload_bytes=100)


if __name__ == "__main__":
    unittest.main()
