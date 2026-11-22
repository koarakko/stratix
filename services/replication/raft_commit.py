"""Conservative current-term commit index gate for an educational Raft leader."""

from .commit_watermark import QuorumWatermarkError, quorum_commit_watermark


def raft_commit_index(voters, acknowledgements, *, term, previous, log_terms, leader_last_index=None):
    """Advance only to a majority-replicated entry from the current term.

    ``log_terms`` is the leader's complete contiguous index-to-term mapping
    from 1 through the majority candidate. The caller must independently
    authenticate matching, durable follower acknowledgements and fence leaders.
    """
    candidate = quorum_commit_watermark(
        voters, acknowledgements, term=term, previous=previous
    )
    if type(log_terms) is not dict:
        raise QuorumWatermarkError("log_terms must be a dictionary")
    if leader_last_index is not None:
        if type(leader_last_index) is not int or leader_last_index < previous or leader_last_index < 0:
            raise QuorumWatermarkError('invalid leader last index')
        if any(index > leader_last_index for _, index in acknowledgements.values()):
            raise QuorumWatermarkError('acknowledgement beyond leader log')
    expected_end = candidate if leader_last_index is None else leader_last_index
    # Reject bool/float aliases: Python considers True == 1 and 1.0 == 1.
    if any(type(index) is not int for index in log_terms):
        raise QuorumWatermarkError('leader log indexes must be integers')
    if set(log_terms) != set(range(1, expected_end + 1)):
        raise QuorumWatermarkError("leader log must cover candidate contiguously")
    last_term = 0
    for index in range(1, expected_end + 1):
        entry_term = log_terms[index]
        if type(entry_term) is not int or not 1 <= entry_term <= term:
            raise QuorumWatermarkError("invalid leader log term")
        if entry_term < last_term:
            raise QuorumWatermarkError("leader log terms must not decrease")
        last_term = entry_term
    if candidate > previous and log_terms[candidate] != term:
        return previous
    return candidate
