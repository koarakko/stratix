"""Bridge verified local log contents to the educational Raft ACK gate."""

from .commit_watermark import QuorumWatermarkError
from .log_integrity import verify
from .log_snapshot import (
    DEFAULT_MAX_LOG_SNAPSHOT_ENTRIES,
    DEFAULT_MAX_LOG_SNAPSHOT_PAYLOAD_BYTES,
    materialize_log_snapshot,
)
from .verified_commit import verified_commit_index


def verified_log_commit_index(
    voters, reports, *, term, previous, log_terms, entries, leader_id=None,
    max_entries=DEFAULT_MAX_LOG_SNAPSHOT_ENTRIES,
    max_payload_bytes=DEFAULT_MAX_LOG_SNAPSHOT_PAYLOAD_BYTES,
):
    """Verify a bounded complete leader chain before evaluating durable ACKs.

    max_entries and max_payload_bytes bound snapshot metadata and payload
    memory. This does not authenticate ACKs, prove fsync, or fence leaders.
    """
    try:
        snapshot = materialize_log_snapshot(
            entries, max_entries=max_entries, max_payload_bytes=max_payload_bytes
        )
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
