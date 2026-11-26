"""Fail-closed v2 term-bound log verification before educational Raft commit gating."""

from .commit_watermark import QuorumWatermarkError
from .term_log import TermLogError, verify_term_log
from .verified_commit import verified_commit_index


def verified_term_commit_index(voters, reports, *, term, previous, entries, leader_id=None):
    """Derive leader terms and hashes exclusively from a verified v2 snapshot.

    Reports are (current_term, durable_index, v2_chain_hash, durable_bool).
    When supplied, leader_id requires that voter's report to cover the full
    local log in the current term. This does not authenticate reports, fsync
    storage, or fence leaders.
    """
    try:
        snapshot = tuple(entries)
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
