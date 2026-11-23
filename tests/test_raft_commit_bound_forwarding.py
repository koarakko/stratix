import unittest
from services.replication.raft_commit import raft_commit_index
from services.replication.commit_watermark import QuorumWatermarkError

class BoundForwardingTests(unittest.TestCase):
    def call(self, indexes, bound=3, previous=0):
        return raft_commit_index(('a','b','c'), dict(zip(('a','b','c'), ((3,i) for i in indexes))), term=3, previous=previous, log_terms={1:1,2:2,3:3}, leader_last_index=bound)

    def test_majority(self):
        self.assertEqual(self.call((3,3,1)),3)

    def test_minority_outlier(self):
        with self.assertRaises(QuorumWatermarkError): self.call((3,3,4))

    def test_invalid_bound(self):
        with self.assertRaises(QuorumWatermarkError): self.call((3,3,1),True)

    def test_previous_greater_than_bound(self):
        with self.assertRaises(QuorumWatermarkError): self.call((3,3,1),2,3)

    def test_retry(self):
        with self.assertRaises(QuorumWatermarkError): self.call((3,3,4))
        self.assertEqual(self.call((3,3,1)),3)

    def test_legacy(self):
        self.assertEqual(raft_commit_index(('a','b','c'), {'a':(3,3),'b':(3,3),'c':(3,1)},term=3,previous=0,log_terms={1:1,2:2,3:3}),3)
