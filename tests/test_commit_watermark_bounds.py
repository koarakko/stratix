import unittest
from services.replication.commit_watermark import QuorumWatermarkError, quorum_commit_watermark


class QuorumBoundTests(unittest.TestCase):
    def test_bounded_majority(self):
        self.assertEqual(quorum_commit_watermark(('a','b','c'), {'a':(2,5),'b':(2,4),'c':(2,1)}, term=2, previous=3, max_index=5), 4)

    def test_any_out_of_range_report_rejected_even_minority(self):
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(('a','b','c'), {'a':(2,4),'b':(2,4),'c':(2,100)}, term=2, max_index=5)

    def test_invalid_bounds(self):
        for bound in (True, 1.0, -1, '5', 2):
            with self.subTest(bound=bound), self.assertRaises(QuorumWatermarkError):
                quorum_commit_watermark(('a',), {'a':(1,3)}, term=1, previous=3, max_index=bound)

    def test_bound_equal_to_previous(self):
        self.assertEqual(quorum_commit_watermark(('a',), {'a':(1,3)}, term=1, previous=3, max_index=3), 3)

    def test_legacy_unbounded_mode(self):
        self.assertEqual(quorum_commit_watermark(('a',), {'a':(1,9)}, term=1), 9)

    def test_retry_after_invalid_snapshot(self):
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(('a',), {'a':(1,8)}, term=1, max_index=7)
        self.assertEqual(quorum_commit_watermark(('a',), {'a':(1,7)}, term=1, max_index=7), 7)
