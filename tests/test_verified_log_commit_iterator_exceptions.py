import unittest

from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.log_integrity import append
from services.replication.verified_log_commit import verified_log_commit_index


class VerifiedLogIteratorExceptionTests(unittest.TestCase):
    def call(self, entries):
        return verified_log_commit_index(
            (), {}, term=1, previous=0, log_terms={}, entries=entries
        )

    def test_iterator_creation_exception_is_normalized(self):
        class BrokenIterable:
            def __iter__(self):
                raise LookupError("log snapshot source failed")

        with self.assertRaises(QuorumWatermarkError) as raised:
            self.call(BrokenIterable())
        self.assertIsInstance(raised.exception.__cause__, LookupError)

    def test_mid_iteration_exception_is_normalized(self):
        first = append((), b"entry")[0]

        def broken_entries():
            yield first
            raise AssertionError("log snapshot stream failed")

        with self.assertRaises(QuorumWatermarkError) as raised:
            self.call(broken_entries())
        self.assertIsInstance(raised.exception.__cause__, AssertionError)

    def test_process_control_exception_propagates(self):
        class InterruptedIterable:
            def __iter__(self):
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            self.call(InterruptedIterable())


if __name__ == "__main__":
    unittest.main()
