import unittest

from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.verified_commit import verified_commit_index


class Impostor:
    def __hash__(self):
        return hash("a")

    def __eq__(self, other):
        return other == "a"


class VoterKeys(unittest.TestCase):
    def calc(self, reports):
        return verified_commit_index(
            ("a", "b", "c"), reports, term=3, previous=0,
            log_terms={1: 3}, leader_hashes={1: "a" * 64},
            leader_last_index=1,
        )

    def valid(self):
        return {
            "a": (3, 1, "a" * 64, True),
            "b": (3, 1, "a" * 64, True),
            "c": (3, 0, None, True),
        }

    def test_valid(self):
        self.assertEqual(self.calc(self.valid()), 1)

    def test_impostor(self):
        reports = self.valid()
        reports[Impostor()] = reports.pop("a")
        with self.assertRaises(QuorumWatermarkError):
            self.calc(reports)

    def test_extra_nonstring_key(self):
        reports = self.valid()
        reports[1] = (3, 0, None, True)
        with self.assertRaises(QuorumWatermarkError):
            self.calc(reports)

    def test_retry(self):
        self.assertEqual(self.calc(self.valid()), self.calc(self.valid()))
