import unittest
from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.verified_commit import verified_commit_index

class Integration(unittest.TestCase):
    def setUp(self):
        self.hashes = {1:'a'*64, 2:'b'*64, 3:'c'*64}
        self.reports = {'leader':(3,3,self.hashes[3],True), 'f1':(3,2,self.hashes[2],True), 'f2':(3,0,None,True)}
    def calc(self, reports=None, **kw):
        args = dict(term=3, previous=0, log_terms={1:1,2:2,3:3}, leader_hashes=self.hashes, leader_last_index=3)
        args.update(kw)
        return verified_commit_index(('leader','f1','f2'), self.reports if reports is None else reports, **args)
    def test_old_term_majority_does_not_advance(self):
        self.assertEqual(self.calc(), 0)
    def test_current_term_majority_advances(self):
        self.assertEqual(self.calc(dict(self.reports, f1=(3,3,self.hashes[3],True))), 3)
    def test_previous_preserved(self):
        self.assertEqual(self.calc(previous=1), 1)
    def test_minority_out_of_bounds_fails(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(dict(self.reports, f2=(3,4,'d'*64,True)))
    def test_minority_hash_mismatch_fails(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(dict(self.reports, f2=(3,1,'f'*64,True)))
    def test_minority_non_durable_fails(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(dict(self.reports, f2=(3,0,None,False)))
    def test_missing_voter_fails(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc({k:v for k,v in self.reports.items() if k != 'f2'})
    def test_incomplete_log_fails(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(dict(self.reports, f1=(3,3,self.hashes[3],True)), log_terms={1:1,3:3})
    def test_retry_after_failure(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(dict(self.reports, f2=(3,0,None,False)))
        self.assertEqual(self.calc(), 0)
        self.assertEqual(self.calc(), 0)
