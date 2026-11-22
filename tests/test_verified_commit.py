import unittest

from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.verified_commit import verified_commit_index


class VerifiedCommitTests(unittest.TestCase):
    def setUp(self):
        self.hashes = {1: 'a' * 64, 2: 'b' * 64, 3: 'c' * 64}
        self.reports = {'a': (3, 3, self.hashes[3], True),
                        'b': (3, 2, self.hashes[2], True),
                        'c': (3, 0, None, True)}

    def calc(self, reports=None, **changes):
        args = dict(term=3, previous=0, log_terms={1: 2, 2: 3, 3: 3},
                    leader_hashes=self.hashes, leader_last_index=3)
        args.update(changes)
        return verified_commit_index(('a', 'b', 'c'),
                                     self.reports if reports is None else reports,
                                     **args)

    def test_majority_current_term(self):
        self.assertEqual(self.calc(), 2)

    def test_old_term_does_not_commit(self):
        self.assertEqual(self.calc(log_terms={1: 1, 2: 2, 3: 3}), 0)

    def test_hash_mismatch_fails_even_on_minority(self):
        reports = dict(self.reports, c=(3, 1, 'f' * 64, True))
        with self.assertRaises(QuorumWatermarkError):
            self.calc(reports)

    def test_non_durable_fails(self):
        reports = dict(self.reports, b=(3, 2, self.hashes[2], False))
        with self.assertRaises(QuorumWatermarkError):
            self.calc(reports)

    def test_missing_report_fails(self):
        reports = dict(self.reports)
        del reports['c']
        with self.assertRaises(QuorumWatermarkError):
            self.calc(reports)

    def test_stale_term_fails(self):
        reports = dict(self.reports, b=(2, 2, self.hashes[2], True))
        with self.assertRaises(QuorumWatermarkError):
            self.calc(reports)

    def test_missing_hash_suffix_fails(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(leader_hashes={1: self.hashes[1], 2: self.hashes[2]})

    def test_bool_hash_index_fails(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(leader_hashes={True: self.hashes[1], 2: self.hashes[2], 3: self.hashes[3]})

    def test_invalid_hash_fails(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(leader_hashes={1: 'A' * 64, 2: self.hashes[2], 3: self.hashes[3]})

    def test_non_boolean_durable_fails(self):
        reports = dict(self.reports, b=(3, 2, self.hashes[2], 1))
        with self.assertRaises(QuorumWatermarkError):
            self.calc(reports)

    def test_zero_index_digest_must_be_none(self):
        reports = dict(self.reports, c=(3, 0, '0' * 64, True))
        with self.assertRaises(QuorumWatermarkError):
            self.calc(reports)

    def test_replay_stable(self):
        self.assertEqual(self.calc(), self.calc())


if __name__ == '__main__':
    unittest.main()
