"""Conservative quorum commit watermark for a fixed, single-term voter set.

Educational calculation only: does not perform leader election, durable writes,
term fencing, or authenticate acknowledgements.
"""


class QuorumWatermarkError(ValueError):
    """Invalid membership or acknowledgement snapshot."""


def strict_majority_size(voter_count):
    """Return the minimum number of votes required for a strict majority."""
    if type(voter_count) is not int or voter_count < 1:
        raise QuorumWatermarkError("voter_count must be a positive integer")
    return voter_count // 2 + 1


def quorum_commit_watermark(voters, acknowledgements, *, term, previous=0, max_index=None):
    """Return the largest index acknowledged by a strict majority.

    Every configured voter must be represented. Missing reports are rejected
    rather than treated as zero, to prevent accidental partial snapshots.
    Callers must independently verify that acknowledgements are authentic,
    durable, and belong to the specified term.
    """
    if type(term) is not int or term < 1:
        raise QuorumWatermarkError("term must be a positive integer")
    if type(previous) is not int or previous < 0:
        raise QuorumWatermarkError("previous must be a nonnegative integer")
    if max_index is not None and (type(max_index) is not int or max_index < previous):
        raise QuorumWatermarkError("max_index must be an integer at least previous")
    if type(voters) in (str, bytes, bytearray, dict):
        raise QuorumWatermarkError("voters must be an iterable of voter names, not a scalar or mapping")
    try:
        members = tuple(voters)
    except Exception as exc:
        # Normalize ordinary iterator failures; process-control exceptions
        # such as KeyboardInterrupt and SystemExit must still propagate.
        raise QuorumWatermarkError("unable to materialize voter membership") from exc
    if not members or any(type(v) is not str or not v.strip() for v in members):
        raise QuorumWatermarkError("voters must be nonempty names")
    if len(set(members)) != len(members):
        raise QuorumWatermarkError("duplicate voter")
    if (type(acknowledgements) is not dict
            or any(type(voter) is not str for voter in acknowledgements)
            or set(acknowledgements) != set(members)):
        raise QuorumWatermarkError("acknowledgements must match voter membership")
    indexes = []
    for voter in members:
        ack = acknowledgements[voter]
        if type(ack) is not tuple or len(ack) != 2:
            raise QuorumWatermarkError("acknowledgement must be (term, index)")
        ack_term, index = ack
        if type(ack_term) is not int or ack_term != term:
            raise QuorumWatermarkError("stale or invalid acknowledgement term")
        if type(index) is not int or index < 0:
            raise QuorumWatermarkError("invalid acknowledgement index")
        if max_index is not None and index > max_index:
            raise QuorumWatermarkError("acknowledgement exceeds local log bound")
        indexes.append(index)
    required = strict_majority_size(len(members))
    candidate = sorted(indexes, reverse=True)[required - 1]
    if candidate < previous:
        raise QuorumWatermarkError("commit watermark regression")
    return candidate
