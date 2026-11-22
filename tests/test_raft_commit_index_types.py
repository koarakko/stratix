"""Reject Python dict-key aliases of Raft log indexes."""
import unittest
from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.raft_commit import raft_commit_index

class RaftCommitIndexTypesTests(unittest.TestCase):
    def calc(self, terms, *, last=None):
        return raft_commit_index(
            ('a', 'b', 'c'), {'a': (3, 1), 'b': (3, 1), 'c': (3, 0)},
            term=3, previous=0, log_terms=terms, leader_last_index=last)

    def test_integer_index_accepted(self):
        self.assertEqual(self.calc({1: 3}), 1)

    def test_bool_index_rejected(self):
        with self.assertRaisesRegex(QuorumWatermarkError, 'indexes must be integers'):
            self.calc({True: 3})

    def test_float_index_rejected(self):
        with self.assertRaisesRegex(QuorumWatermarkError, 'indexes must be integers'):
            self.calc({1.0: 3}, last=1)

    def test_string_index_rejected(self):
        with self.assertRaisesRegex(QuorumWatermarkError, 'indexes must be integers'):
            self.calc({'1': 3})

    def test_mixed_alias_index_rejected(self):
        with self.assertRaisesRegex(QuorumWatermarkError, 'indexes must be integers'):
            self.calc({1: 3, 2.0: 3}, last=2)

if __name__ == '__main__':
    unittest.main()
