"""Bridge verified local log contents to the educational Raft ACK gate."""

from .commit_watermark import QuorumWatermarkError
from .log_integrity import LogIntegrityError, verify
from .verified_commit import verified_commit_index


def verified_log_commit_index(voters, reports, *, term, previous, log_terms, entries, leader_id=None):
    """Verify the complete leader chain before evaluating supplied durable ACKs.

    This does not authenticate ACKs, prove fsync, or provide leader fencing.
    """
    try:
        snapshot = tuple(entries)
        verify(snapshot)
    except Exception as exc:
        # A hostile or failing iterable must not bypass the fail-closed API.
        # BaseException subclasses used for process control still propagate.
        raise QuorumWatermarkError('invalid leader log snapshot') from exc
    return verified_commit_index(
        voters, reports, term=term, previous=previous, log_terms=log_terms,
        leader_hashes={entry.sequence: entry.entry_hash for entry in snapshot},
        leader_last_index=len(snapshot), leader_id=leader_id,
    )
