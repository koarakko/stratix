import unittest
from services.replication.verified_commit import verified_commit_index
from services.replication.commit_watermark import QuorumWatermarkError

class LeaderSelfAck(unittest.TestCase):
    def setUp(self):
        self.h = {1:'a'*64,2:'b'*64}
        self.reports = {'leader':(2,2,self.h[2],True),'f1':(2,2,self.h[2],True),'f2':(2,0,None,True)}
    def calc(self, reports=None, **extra):
        kw = dict(term=2, previous=0, log_terms={1:1,2:2}, leader_hashes=self.h, leader_last_index=2, leader_id='leader')
        kw.update(extra)
        return verified_commit_index(('leader','f1','f2'),self.reports if reports is None else reports,**kw)
    def test_full_self_ack(self):
        self.assertEqual(self.calc(),2)
    def test_underreported_leader(self):
        with self.assertRaises(QuorumWatermarkError): self.calc(dict(self.reports,leader=(2,1,self.h[1],True)))
    def test_missing_leader(self):
        with self.assertRaises(QuorumWatermarkError): self.calc(dict(self.reports,leader_missing=(2,2,self.h[2],True)))
    def test_stale_leader(self):
        with self.assertRaises(QuorumWatermarkError): self.calc(dict(self.reports,leader=(1,2,self.h[2],True)))
    def test_invalid_leader_id(self):
        for value in ('',True,1,[], '  '):
            with self.subTest(value=value), self.assertRaises(QuorumWatermarkError): self.calc(leader_id=value)
    def test_retry_after_failure(self):
        with self.assertRaises(QuorumWatermarkError): self.calc(dict(self.reports,leader=(2,1,self.h[1],True)))
        self.assertEqual(self.calc(),2)
    def test_legacy_omitted_id(self):
        self.assertEqual(self.calc(leader_id=None),2)
    def test_zero_length_log(self):
        self.assertEqual(verified_commit_index(('leader',),{'leader':(2,0,None,True)},term=2,previous=0,log_terms={},leader_hashes={},leader_last_index=0,leader_id='leader'),0)
