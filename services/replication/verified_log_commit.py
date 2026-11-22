"""Bridge verified local log contents to the educational Raft ACK gate."""

from .commit_watermark import QuorumWatermarkError
from .log_integrity import LogIntegrityError, verify
from .verified_commit import verified_commit_index


def verified_log_commit_index(voters, reports, *, term, previous, log_terms, entries):
    """Verify the complete leader chain before evaluating supplied durable ACKs.

    This does not authenticate ACKs, prove fsync, or provide leader fencing.
    """
    try:
        snapshot = tuple(entries)
        verify(snapshot)
    except (LogIntegrityError, TypeError, ValueError, OverflowError, OSError, RuntimeError) as exc:
        raise QuorumWatermarkError('invalid leader log snapshot') from exc
    return verified_commit_index(
        voters, reports, term=term, previous=previous, log_terms=log_terms,
        leader_hashes={entry.sequence: entry.entry_hash for entry in snapshot},
        leader_last_index=len(snapshot),
    )
