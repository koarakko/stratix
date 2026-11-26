import unittest

from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.term_log import append_term
from services.replication.verified_term_commit import verified_term_commit_index


class VerifiedTermIteratorExceptionTests(unittest.TestCase):
    def call(self, entries):
        return verified_term_commit_index((), {}, term=1, previous=0, entries=entries)

    def test_iterator_creation_exception_is_normalized(self):
        class BrokenIterable:
            def __iter__(self):
                raise LookupError("term log snapshot source failed")

        with self.assertRaises(QuorumWatermarkError) as raised:
            self.call(BrokenIterable())
        self.assertIsInstance(raised.exception.__cause__, LookupError)

    def test_mid_iteration_exception_is_normalized(self):
        first = append_term((), 1, b"entry")[0]

        def broken_entries():
            yield first
            raise AssertionError("term log snapshot stream failed")

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
