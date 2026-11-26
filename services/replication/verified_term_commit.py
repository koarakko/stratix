"""Fail-closed v2 term-bound log verification before educational Raft commit gating."""

from .commit_watermark import QuorumWatermarkError
from .log_snapshot import (
    DEFAULT_MAX_LOG_SNAPSHOT_ENTRIES,
    DEFAULT_MAX_LOG_SNAPSHOT_PAYLOAD_BYTES,
    materialize_log_snapshot,
)
from .term_log import verify_term_log
from .verified_commit import verified_commit_index


def verified_term_commit_index(
    voters, reports, *, term, previous, entries, leader_id=None,
    max_entries=DEFAULT_MAX_LOG_SNAPSHOT_ENTRIES,
    max_payload_bytes=DEFAULT_MAX_LOG_SNAPSHOT_PAYLOAD_BYTES,
):
    """Derive leader terms and hashes from one bounded verified snapshot.

    max_entries and max_payload_bytes bound snapshot metadata and payload
    memory. This does not authenticate reports, fsync storage, or fence leaders.
    """
    try:
        snapshot = materialize_log_snapshot(
            entries, max_entries=max_entries, max_payload_bytes=max_payload_bytes
        )
        verify_term_log(snapshot)
    except Exception as exc:
        # Normalize ordinary iterator and verifier failures at the API boundary.
        # BaseException subclasses used for process control still propagate.
        raise QuorumWatermarkError('invalid term-bound leader log snapshot') from exc
    return verified_commit_index(
        voters, reports, term=term, previous=previous,
        log_terms={entry.sequence: entry.term for entry in snapshot},
        leader_hashes={entry.sequence: entry.entry_hash for entry in snapshot},
        leader_last_index=len(snapshot), leader_id=leader_id,
    )
