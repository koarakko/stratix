"""Fail-closed preflight for durable, hash-chain-bound Raft acknowledgements.

This validates supplied evidence, not its authenticity or disk persistence.
"""

import re

from .commit_watermark import QuorumWatermarkError
from .raft_commit import raft_commit_index

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def verified_commit_index(voters, reports, *, term, previous, log_terms,
                          leader_hashes, leader_last_index):
    """Calculate a Raft commit index from validated hash-chain ACK snapshots.

    Each report is (term, index, chain_hash, durable). The hash must be a
    SHA-256 lowercase hex digest of the leader's *cumulative* log chain at
    that index. Index zero uses None. The leader is included in voters.
    """
    if type(reports) is not dict or type(leader_hashes) is not dict:
        raise QuorumWatermarkError("reports and leader_hashes must be dictionaries")
    if type(leader_last_index) is not int or leader_last_index < 0:
        raise QuorumWatermarkError("invalid leader last index")
    if any(type(i) is not int for i in leader_hashes):
        raise QuorumWatermarkError("invalid hash index type")
    if set(leader_hashes) != set(range(1, leader_last_index + 1)):
        raise QuorumWatermarkError("leader hashes must cover full log")
    if any(type(h) is not str or _DIGEST.fullmatch(h) is None
           for h in leader_hashes.values()):
        raise QuorumWatermarkError("invalid leader chain hash")
    acknowledgements = {}
    for voter, report in reports.items():
        if type(report) is not tuple or len(report) != 4:
            raise QuorumWatermarkError("invalid durable report")
        ack_term, index, digest, durable = report
        if type(durable) is not bool or not durable:
            raise QuorumWatermarkError("non-durable acknowledgement")
        if type(index) is not int or index < 0 or index > leader_last_index:
            raise QuorumWatermarkError("invalid acknowledged index")
        if digest != (None if index == 0 else leader_hashes[index]):
            raise QuorumWatermarkError("acknowledged log hash mismatch")
        acknowledgements[voter] = (ack_term, index)
    return raft_commit_index(
        voters, acknowledgements, term=term, previous=previous,
        log_terms=log_terms, leader_last_index=leader_last_index,
    )
