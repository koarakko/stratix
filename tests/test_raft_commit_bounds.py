import unittest
from services.replication.raft_commit import raft_commit_index
from services.replication.commit_watermark import QuorumWatermarkError

class RaftCommitBoundsTests(unittest.TestCase):
    def calc(self, indexes, terms, last):
        return raft_commit_index(('a','b','c'), dict(zip(('a','b','c'), ((3,i) for i in indexes))), term=3, previous=0, log_terms=terms, leader_last_index=last)
    def test_valid_suffix(self):
        self.assertEqual(self.calc((2,2,1),{1:2,2:3,3:3},3),2)
    def test_minority_ahead(self):
        with self.assertRaises(QuorumWatermarkError): self.calc((100,2,2),{1:2,2:3,3:3},3)
    def test_missing_suffix(self):
        with self.assertRaises(QuorumWatermarkError): self.calc((2,2,1),{1:2,2:3},3)
    def test_invalid_suffix_term(self):
        with self.assertRaises(QuorumWatermarkError): self.calc((2,2,1),{1:2,2:3,3:4},3)
    def test_bool_last(self):
        with self.assertRaises(QuorumWatermarkError): self.calc((0,0,0),{},True)
    def test_negative_last(self):
        with self.assertRaises(QuorumWatermarkError): self.calc((0,0,0),{},-1)
    def test_empty(self):
        self.assertEqual(self.calc((0,0,0),{},0),0)
    def test_old_term(self):
        self.assertEqual(self.calc((1,1,0),{1:2,2:3},2),0)
if __name__ == '__main__': unittest.main()
