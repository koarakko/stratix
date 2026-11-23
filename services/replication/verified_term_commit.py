"""Fail-closed v2 term-bound log verification before educational Raft commit gating."""

from .commit_watermark import QuorumWatermarkError
from .term_log import TermLogError, verify_term_log
from .verified_commit import verified_commit_index


def verified_term_commit_index(voters, reports, *, term, previous, entries):
    """Derive leader terms and hashes exclusively from a verified v2 snapshot.

    Reports are (current_term, durable_index, v2_chain_hash, durable_flag).
    This does not authenticate reports, fsync storage, or fence leaders.
    """
    try:
        snapshot = tuple(entries)
        verify_term_log(snapshot)
    except (TermLogError, TypeError, ValueError, OverflowError, OSError, RuntimeError) as exc:
        raise QuorumWatermarkError('invalid term-bound leader log snapshot') from exc
    return verified_commit_index(
        voters, reports, term=term, previous=previous,
        log_terms={entry.sequence: entry.term for entry in snapshot},
        leader_hashes={entry.sequence: entry.entry_hash for entry in snapshot},
        leader_last_index=len(snapshot),
    )
