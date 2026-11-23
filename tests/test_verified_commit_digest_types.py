import unittest

from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.verified_commit import verified_commit_index


class FakeEqual:
    def __eq__(self, other):
        return True


class DigestTypes(unittest.TestCase):
    def calc(self, digest, index=1):
        return verified_commit_index(
            ('a', 'b', 'c'),
            {'a': (3, index, digest, True),
             'b': (3, 1, 'a' * 64, True),
             'c': (3, 0, None, True)},
            term=3, previous=0, log_terms={1: 3},
            leader_hashes={1: 'a' * 64}, leader_last_index=1,
        )

    def test_valid_digest(self):
        self.assertEqual(self.calc('a' * 64), 1)

    def test_zero_none(self):
        self.assertEqual(self.calc(None, 0), 0)

    def test_zero_fake_equal(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(FakeEqual(), 0)

    def test_positive_fake_equal(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(FakeEqual())

    def test_positive_none(self):
        with self.assertRaises(QuorumWatermarkError):
            self.calc(None)

    def test_invalid_digest_forms(self):
        for digest in ('A' * 64, 'a' * 63, 'a' * 65,
                       'g' * 64, b'a' * 64, 1, True, ['a' * 64]):
            with self.subTest(digest=digest), self.assertRaises(QuorumWatermarkError):
                self.calc(digest)

    def test_retry_deterministic(self):
        self.assertEqual(self.calc('a' * 64), self.calc('a' * 64))
