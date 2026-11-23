import unittest
from services.replication.commit_watermark import QuorumWatermarkError, quorum_commit_watermark


class QuorumWatermarkTests(unittest.TestCase):
    def test_three_voter_majority(self):
        self.assertEqual(quorum_commit_watermark(('a', 'b', 'c'), {'a': (2, 9), 'b': (2, 7), 'c': (2, 1)}, term=2), 7)

    def test_four_voter_majority_requires_three(self):
        self.assertEqual(quorum_commit_watermark(('a', 'b', 'c', 'd'), {'a': (1, 8), 'b': (1, 8), 'c': (1, 4), 'd': (1, 0)}, term=1), 4)

    def test_single_voter(self):
        self.assertEqual(quorum_commit_watermark(('a',), {'a': (1, 3)}, term=1), 3)

    def test_missing_voter_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(('a', 'b', 'c'), {'a': (1, 8), 'b': (1, 8)}, term=1)

    def test_extra_voter_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(('a',), {'a': (1, 1), 'b': (1, 1)}, term=1)

    def test_duplicate_membership_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(('a', 'a'), {'a': (1, 2)}, term=1)

    def test_stale_term_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(('a', 'b'), {'a': (2, 3), 'b': (1, 3)}, term=2)

    def test_watermark_regression_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(('a',), {'a': (1, 2)}, term=1, previous=3)

    def test_invalid_types_rejected(self):
        for value in (True, -1, 1.0, None):
            with self.subTest(value=value), self.assertRaises(QuorumWatermarkError):
                quorum_commit_watermark(('a',), {'a': (1, value)}, term=1)

    def test_no_quorum_progress(self):
        self.assertEqual(quorum_commit_watermark(('a', 'b', 'c'), {'a': (1, 7), 'b': (1, 0), 'c': (1, 0)}, term=1), 0)

    def test_voter_key_spoofing_rejected(self):
        class Impostor:
            def __hash__(self):
                return hash('a')

            def __eq__(self, other):
                return other == 'a'

        reports = {'a': (2, 4), 'b': (2, 3), 'c': (2, 0)}
        reports[Impostor()] = reports.pop('a')
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(('a', 'b', 'c'), reports, term=2)

    def test_extra_nonstring_voter_key_rejected(self):
        reports = {'a': (2, 4), 'b': (2, 3), 'c': (2, 0), 1: (2, 0)}
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(('a', 'b', 'c'), reports, term=2)

    def test_scalar_membership_rejected_even_if_reports_match_characters(self):
        reports = {'a': (1, 4), 'b': (1, 4), 'c': (1, 0)}
        for voters in ('abc', b'abc', bytearray(b'abc')):
            with self.subTest(voters=voters), self.assertRaises(QuorumWatermarkError):
                quorum_commit_watermark(voters, reports, term=1)

    def test_mapping_membership_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark({'a': True, 'b': True}, {'a': (1, 2), 'b': (1, 2)}, term=1)

    def test_tuple_and_generator_membership_still_supported(self):
        reports = {'a': (1, 3), 'b': (1, 2), 'c': (1, 0)}
        self.assertEqual(quorum_commit_watermark(('a', 'b', 'c'), reports, term=1), 2)
        self.assertEqual(quorum_commit_watermark((v for v in ('a', 'b', 'c')), reports, term=1), 2)

    def test_valid_snapshot_retry(self):
        reports = {'a': (2, 4), 'b': (2, 3), 'c': (2, 0)}
        self.assertEqual(quorum_commit_watermark(('a', 'b', 'c'), reports, term=2), 3)
        self.assertEqual(quorum_commit_watermark(('a', 'b', 'c'), reports, term=2), 3)



if __name__ == '__main__':
    unittest.main()
