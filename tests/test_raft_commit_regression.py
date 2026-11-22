"""Regression coverage for the Raft current-term gate and malformed index inputs."""
import unittest
from services.replication.raft_commit import raft_commit_index
from services.replication.commit_watermark import QuorumWatermarkError


class RaftCommitRegressionTests(unittest.TestCase):
    def calc(self, indexes, terms, *, previous=0, last=None):
        acknowledgements = dict(zip(('a', 'b', 'c'), ((3, i) for i in indexes)))
        return raft_commit_index(
            ('a', 'b', 'c'), acknowledgements, term=3, previous=previous,
            log_terms=terms, leader_last_index=last,
        )

    def test_current_term(self):
        self.assertEqual(self.calc((2, 2, 0), {1: 2, 2: 3}), 2)

    def test_old_term(self):
        self.assertEqual(self.calc((1, 1, 0), {1: 2}), 0)

    def test_empty(self):
        self.assertEqual(self.calc((0, 0, 0), {}), 0)

    def test_bool_key(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((1, 1, 0), {True: 3})

    def test_float_key(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((1, 1, 0), {1.0: 3})

    def test_bad_suffix(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((1, 1, 0), {1: 3}, last=2)

    def test_minority_beyond_leader(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc((5, 1, 1), {1: 3}, last=1)

    def test_previous(self):
        self.assertEqual(self.calc((1, 1, 1), {1: 3}, previous=1), 1)


if __name__ == '__main__':
    unittest.main()
