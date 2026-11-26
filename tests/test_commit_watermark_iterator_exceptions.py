import unittest

from services.replication.commit_watermark import (
    QuorumWatermarkError,
    quorum_commit_watermark,
)


class MembershipIteratorExceptionTests(unittest.TestCase):
    def test_iterator_creation_exception_is_normalized(self):
        class BrokenIterable:
            def __iter__(self):
                raise LookupError("membership source failed")

        with self.assertRaises(QuorumWatermarkError) as raised:
            quorum_commit_watermark(BrokenIterable(), {}, term=1)
        self.assertIsInstance(raised.exception.__cause__, LookupError)

    def test_mid_iteration_exception_is_normalized(self):
        def broken_members():
            yield "leader"
            raise AssertionError("membership stream failed")

        with self.assertRaises(QuorumWatermarkError) as raised:
            quorum_commit_watermark(broken_members(), {"leader": (1, 1)}, term=1)
        self.assertIsInstance(raised.exception.__cause__, AssertionError)

    def test_process_control_exception_propagates(self):
        class InterruptedIterable:
            def __iter__(self):
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            quorum_commit_watermark(InterruptedIterable(), {}, term=1)


if __name__ == "__main__":
    unittest.main()
