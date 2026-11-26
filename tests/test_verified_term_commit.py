import unittest
from dataclasses import replace
from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.term_log import append_term, GENESIS
from services.replication.verified_term_commit import verified_term_commit_index


class VerifiedTermCommitTests(unittest.TestCase):
    def setUp(self):
        self.entries = append_term(append_term(append_term((), 2, b'a'), 3, b'b'), 3, b'c')
        self.reports = {'a': (3, 3, self.entries[2].entry_hash, True),
                        'b': (3, 2, self.entries[1].entry_hash, True),
                        'c': (3, 0, None, True)}

    def calc(self, **overrides):
        args = dict(term=3, previous=0, entries=self.entries)
        args.update(overrides)
        return verified_term_commit_index(('a', 'b', 'c'), self.reports, **args)

    def test_current_term_majority(self):
        self.assertEqual(self.calc(), 2)

    def test_deterministic_retry(self):
        self.assertEqual(self.calc(), self.calc())

    def test_old_term_majority_does_not_commit(self):
        reports = {'a': (3, 3, self.entries[2].entry_hash, True),
                   'b': (3, 1, self.entries[0].entry_hash, True),
                   'c': (3, 1, self.entries[0].entry_hash, True)}
        self.assertEqual(verified_term_commit_index(tuple(reports), reports, term=3, previous=0, entries=self.entries), 0)

    def test_existing_commit_retained(self):
        self.assertEqual(self.calc(previous=1), 2)

    def test_empty_log(self):
        reports = {name: (3, 0, None, True) for name in self.reports}
        self.assertEqual(verified_term_commit_index(tuple(reports), reports, term=3, previous=0, entries=()), 0)

    def test_term_tampering(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(entries=(replace(self.entries[0], term=3),) + self.entries[1:])

    def test_payload_tampering(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(entries=(replace(self.entries[0], payload=b'evil'),) + self.entries[1:])

    def test_broken_link(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(entries=(self.entries[0], replace(self.entries[1], previous_hash=GENESIS), self.entries[2]))

    def test_truncated_log_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(entries=self.entries[:2])

    def test_wrong_hash_rejected(self):
        reports = dict(self.reports, b=(3, 2, self.entries[0].entry_hash, True))
        with self.assertRaises(QuorumWatermarkError):
            verified_term_commit_index(tuple(reports), reports, term=3, previous=0, entries=self.entries)

    def test_non_durable_ack_rejected(self):
        reports = dict(self.reports, c=(3, 0, None, False))
        with self.assertRaises(QuorumWatermarkError):
            verified_term_commit_index(tuple(reports), reports, term=3, previous=0, entries=self.entries)

    def test_stale_ack_term_rejected(self):
        reports = dict(self.reports, c=(2, 0, None, True))
        with self.assertRaises(QuorumWatermarkError):
            verified_term_commit_index(tuple(reports), reports, term=3, previous=0, entries=self.entries)

    def test_missing_voter_rejected(self):
        reports = dict(self.reports)
        del reports['c']
        with self.assertRaises(QuorumWatermarkError):
            verified_term_commit_index(('a', 'b', 'c'), reports, term=3, previous=0, entries=self.entries)

    def test_invalid_snapshot_rejected(self):
        for entries in (None, (object(),), self.entries[::-1]):
            with self.subTest(entries=entries), self.assertRaises(QuorumWatermarkError):
                self.calc(entries=entries)

    def test_index_bool_rejected(self):
        reports = dict(self.reports, c=(3, True, self.entries[0].entry_hash, True))
        with self.assertRaises(QuorumWatermarkError):
            verified_term_commit_index(tuple(reports), reports, term=3, previous=0, entries=self.entries)

    def test_no_external_term_mapping(self):
        with self.assertRaises(TypeError):
            self.calc(log_terms={1: 3, 2: 3, 3: 3})



    def test_explicit_leader_must_ack_full_log_in_current_term(self):
        self.assertEqual(self.calc(leader_id='a'), 2)

    def test_underreported_leader_rejected_even_when_other_voter_is_ahead(self):
        reports = dict(self.reports, a=(3, 2, self.entries[1].entry_hash, True))
        with self.assertRaises(QuorumWatermarkError):
            verified_term_commit_index(('a', 'b', 'c'), reports, term=3,
                                       previous=0, entries=self.entries, leader_id='a')

    def test_missing_named_leader_report_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(leader_id='unknown-leader')

    def test_stale_named_leader_report_rejected(self):
        reports = dict(self.reports, a=(2, 3, self.entries[2].entry_hash, True))
        with self.assertRaises(QuorumWatermarkError):
            verified_term_commit_index(('a', 'b', 'c'), reports, term=3,
                                       previous=0, entries=self.entries, leader_id='a')

    def test_invalid_leader_id_rejected(self):
        for leader_id in ('', '  ', True, 1, []):
            with self.subTest(leader_id=leader_id), self.assertRaises(QuorumWatermarkError):
                self.calc(leader_id=leader_id)

    def test_retry_after_leader_self_ack_failure(self):
        reports = dict(self.reports, a=(3, 1, self.entries[0].entry_hash, True))
        with self.assertRaises(QuorumWatermarkError):
            verified_term_commit_index(('a', 'b', 'c'), reports, term=3,
                                       previous=0, entries=self.entries, leader_id='a')
        self.assertEqual(self.calc(leader_id='a'), 2)

    def test_zero_length_log_with_explicit_leader(self):
        reports = {'leader': (3, 0, None, True)}
        self.assertEqual(verified_term_commit_index(('leader',), reports, term=3,
                         previous=0, entries=(), leader_id='leader'), 0)


if __name__ == '__main__':
    unittest.main()
