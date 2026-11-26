"""Exhaustive bounded checks for strict-majority watermark selection."""
import itertools
import unittest

from services.replication.commit_watermark import (
    QuorumWatermarkError,
    quorum_commit_watermark,
    strict_majority_size,
)


class StrictMajorityProperties(unittest.TestCase):
    def test_required_count_for_odd_and_even_memberships(self):
        for count in range(1, 33):
            with self.subTest(count=count):
                self.assertEqual(strict_majority_size(count), count // 2 + 1)

    def test_invalid_voter_counts_fail_closed(self):
        for value in (True, False, 0, -1, 1.0, "3", None):
            with self.subTest(value=value), self.assertRaises(QuorumWatermarkError):
                strict_majority_size(value)

    def test_exhaustive_ack_vectors_match_strict_majority_definition(self):
        # For 1..7 voters and ACK indexes 0..3, compare the implementation
        # with the definition: an index is committed iff >= floor(n/2)+1
        # voters have acknowledged at least that index.
        for count in range(1, 8):
            voters = tuple(f"v{i}" for i in range(count))
            required = count // 2 + 1
            for indexes in itertools.product(range(4), repeat=count):
                acknowledgements = {
                    voter: (9, index)
                    for voter, index in zip(voters, indexes)
                }
                expected = max(
                    candidate
                    for candidate in range(4)
                    if sum(index >= candidate for index in indexes) >= required
                )
                actual = quorum_commit_watermark(
                    voters, acknowledgements, term=9
                )
                self.assertEqual(actual, expected, (count, indexes))

    def test_result_is_independent_of_voter_and_mapping_order(self):
        for indexes in ((5,), (5, 2), (5, 2, 0), (5, 4, 3, 0),
                        (7, 6, 2, 1, 0), (4, 4, 4, 4, 0, 0)):
            voters = tuple(f"v{i}" for i in range(len(indexes)))
            reports = {
                voter: (4, index)
                for voter, index in zip(voters, indexes)
            }
            expected = quorum_commit_watermark(voters, reports, term=4)
            reversed_reports = dict(reversed(tuple(reports.items())))
            actual = quorum_commit_watermark(
                tuple(reversed(voters)), reversed_reports, term=4
            )
            self.assertEqual(actual, expected)

    def test_ack_growth_never_reduces_candidate(self):
        # Increasing any one ACK while holding membership and term fixed must
        # not move the order-statistic watermark backwards.
        for count in range(1, 7):
            voters = tuple(f"v{i}" for i in range(count))
            for indexes in itertools.product(range(3), repeat=count):
                reports = {
                    voter: (5, index)
                    for voter, index in zip(voters, indexes)
                }
                before = quorum_commit_watermark(voters, reports, term=5)
                for position, voter in enumerate(voters):
                    advanced = dict(reports)
                    advanced[voter] = (5, indexes[position] + 1)
                    after = quorum_commit_watermark(voters, advanced, term=5)
                    self.assertGreaterEqual(after, before, (count, indexes, voter))

    def test_even_cluster_requires_more_than_half(self):
        voters = ("a", "b", "c", "d")
        reports = {
            "a": (2, 100),
            "b": (2, 100),
            "c": (2, 0),
            "d": (2, 0),
        }
        self.assertEqual(quorum_commit_watermark(voters, reports, term=2), 0)


if __name__ == "__main__":
    unittest.main()
