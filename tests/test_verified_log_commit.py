import unittest
from dataclasses import replace
from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.log_integrity import append, GENESIS
from services.replication.verified_log_commit import verified_log_commit_index

class VerifiedLogCommitTests(unittest.TestCase):
    def setUp(self):
        self.entries = append(append(append((), b'a'), b'b'), b'c')
        self.reports = {'a': (3, 3, self.entries[2].entry_hash, True),
                        'b': (3, 2, self.entries[1].entry_hash, True),
                        'c': (3, 0, None, True)}
    def calc(self, **kwargs):
        args = dict(term=3, previous=0, log_terms={1: 2, 2: 3, 3: 3}, entries=self.entries)
        args.update(kwargs)
        return verified_log_commit_index(('a','b','c'), self.reports, **args)
    def test_majority(self): self.assertEqual(self.calc(), 2)
    def test_repeat(self): self.assertEqual(self.calc(), self.calc())
    def test_old_term(self): self.assertEqual(self.calc(log_terms={1:1,2:2,3:3}),0)
    def test_empty_log(self):
        reports={k:(3,0,None,True) for k in self.reports}
        self.assertEqual(verified_log_commit_index(tuple(reports),reports,term=3,previous=0,log_terms={},entries=()),0)
    def test_payload_tamper(self):
        altered=(replace(self.entries[0],payload=b'bad'),)+self.entries[1:]
        with self.assertRaises(QuorumWatermarkError): self.calc(entries=altered)
    def test_broken_link(self):
        altered=(self.entries[0],replace(self.entries[1],previous_hash=GENESIS),self.entries[2])
        with self.assertRaises(QuorumWatermarkError): self.calc(entries=altered)
    def test_truncated(self):
        with self.assertRaises(QuorumWatermarkError): self.calc(entries=self.entries[:2])
    def test_reordered(self):
        with self.assertRaises(QuorumWatermarkError): self.calc(entries=self.entries[::-1])
    def test_non_durable(self):
        reports=dict(self.reports,b=(3,2,self.entries[1].entry_hash,False))
        with self.assertRaises(QuorumWatermarkError):
            verified_log_commit_index(tuple(reports),reports,term=3,previous=0,log_terms={1:2,2:3,3:3},entries=self.entries)
    def test_bad_iterable(self):
        with self.assertRaises(QuorumWatermarkError): self.calc(entries=None)
    def test_bad_entry(self):
        with self.assertRaises(QuorumWatermarkError): self.calc(entries=(object(),))
    def test_missing_term(self):
        with self.assertRaises(QuorumWatermarkError): self.calc(log_terms={1:2,2:3})

if __name__=='__main__': unittest.main()
