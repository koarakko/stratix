import unittest

from services.replication.commit_watermark import QuorumWatermarkError
from services.replication.raft_commit import raft_commit_index
from services.replication.verified_commit import verified_commit_index


class RaftLogContiguityTests(unittest.TestCase):
    def test_raft_rejects_huge_unmaterialized_log_bound(self):
        # A range/set-based check would attempt to materialize an enormous set.
        with self.assertRaises(QuorumWatermarkError):
            raft_commit_index(
                ("leader",),
                {"leader": (3, 0)},
                term=3,
                previous=0,
                log_terms={},
                leader_last_index=10**12,
            )

    def test_raft_rejects_same_cardinality_out_of_range_key(self):
        with self.assertRaises(QuorumWatermarkError):
            raft_commit_index(
                ("leader",),
                {"leader": (3, 3)},
                term=3,
                previous=0,
                log_terms={1: 1, 2: 2, 4: 3},
                leader_last_index=3,
            )

    def test_raft_accepts_complete_contiguous_log(self):
        self.assertEqual(
            raft_commit_index(
                ("leader",),
                {"leader": (3, 3)},
                term=3,
                previous=0,
                log_terms={1: 1, 2: 2, 3: 3},
                leader_last_index=3,
            ),
            3,
        )

    def test_verified_commit_rejects_huge_hash_bound(self):
        # The hash-map preflight must fail before constructing a range.
        with self.assertRaises(QuorumWatermarkError):
            verified_commit_index(
                ("leader",),
                {},
                term=3,
                previous=0,
                log_terms={},
                leader_hashes={},
                leader_last_index=10**12,
            )

    def test_verified_commit_rejects_same_cardinality_out_of_range_hash(self):
        with self.assertRaises(QuorumWatermarkError):
            verified_commit_index(
                ("leader",),
                {},
                term=3,
                previous=0,
                log_terms={1: 1, 2: 2, 3: 3},
                leader_hashes={1: "a" * 64, 2: "b" * 64, 4: "d" * 64},
                leader_last_index=3,
            )

    def test_verified_commit_rejects_sparse_term_map_after_hash_validation(self):
        digest = "c" * 64
        with self.assertRaises(QuorumWatermarkError):
            verified_commit_index(
                ("leader",),
                {"leader": (3, 3, digest, True)},
                term=3,
                previous=0,
                log_terms={1: 1, 2: 2, 4: 3},
                leader_hashes={1: "a" * 64, 2: "b" * 64, 3: digest},
                leader_last_index=3,
            )


if __name__ == "__main__":
    unittest.main()
