import unittest
from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.raft_commit import raft_commit_index


class RaftCommitTests(unittest.TestCase):
    def calc(self, indexes, log_terms, *, term=3, previous=0):
        return raft_commit_index(('a', 'b', 'c'),
            dict(zip(('a', 'b', 'c'), ((term, i) for i in indexes))),
            term=term, previous=previous, log_terms=log_terms)

    def test_current_term_majority_advances(self):
        self.assertEqual(self.calc((3, 3, 1), {1: 1, 2: 2, 3: 3}), 3)

    def test_old_term_majority_does_not_advance(self):
        self.assertEqual(self.calc((2, 2, 0), {1: 1, 2: 2}), 0)

    def test_old_term_majority_preserves_previous(self):
        self.assertEqual(self.calc((2, 2, 1), {1: 1, 2: 2}, previous=1), 1)

    def test_current_term_entry_commits_prior_entries(self):
        self.assertEqual(self.calc((4, 4, 0), {1: 1, 2: 1, 3: 2, 4: 3}), 4)

    def test_no_majority_progress(self):
        self.assertEqual(self.calc((2, 0, 0), {}, previous=0), 0)

    def test_regression_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((0, 0, 2), {}, previous=1)

    def test_missing_entry_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((3, 3, 0), {1: 1, 3: 3})

    def test_extra_entry_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((1, 1, 0), {1: 3, 2: 3})

    def test_future_term_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((1, 1, 0), {1: 4})

    def test_non_monotonic_term_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((2, 2, 0), {1: 2, 2: 1})

    def test_bool_term_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((1, 1, 0), {1: True})

    def test_invalid_acknowledgement_rejected(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((1, 1, 0), {1: 3}, term=2)


if __name__ == '__main__':
    unittest.main()
