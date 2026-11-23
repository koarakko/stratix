import unittest
from services.replication.commit_watermark import QuorumWatermarkError, quorum_commit_watermark

class MembershipIteratorTests(unittest.TestCase):
    def test_iterator_runtime_failure_normalized(self):
        def broken():
            yield 'a'
            raise RuntimeError('membership source unavailable')
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(broken(), {'a': (1, 1)}, term=1)

    def test_iterator_value_failure_normalized(self):
        def broken():
            yield 'a'
            raise ValueError('corrupt membership')
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(broken(), {'a': (1, 1)}, term=1)

    def test_generator_success_retry(self):
        reports = {'a': (1, 4), 'b': (1, 3), 'c': (1, 0)}
        for _ in range(2):
            self.assertEqual(quorum_commit_watermark((v for v in ('a','b','c')), reports, term=1), 3)

    def test_iterator_io_failure_normalized(self):
        def broken():
            yield 'a'
            raise OSError('membership read failed')
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(broken(), {'a': (1, 1)}, term=1)

    def test_io_failure_then_fresh_retry(self):
        def broken():
            yield 'a'
            raise OSError('transient membership failure')
        reports = {'a': (2, 5), 'b': (2, 4), 'c': (2, 0)}
        with self.assertRaises(QuorumWatermarkError):
            quorum_commit_watermark(broken(), reports, term=2)
        self.assertEqual(quorum_commit_watermark(iter(('a', 'b', 'c')), reports, term=2), 4)
