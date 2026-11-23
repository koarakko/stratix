"""Conservative quorum commit watermark for a fixed, single-term voter set.

Educational calculation only: does not perform leader election, durable writes,
term fencing, or authenticate acknowledgements.
"""


class QuorumWatermarkError(ValueError):
    """Invalid membership or acknowledgement snapshot."""


def quorum_commit_watermark(voters, acknowledgements, *, term, previous=0):
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
    if type(voters) in (str, bytes, bytearray, dict):
        raise QuorumWatermarkError("voters must be an iterable of voter names, not a scalar or mapping")
    try:
        members = tuple(voters)
    except (TypeError, ValueError, RuntimeError) as exc:
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
        indexes.append(index)
    candidate = sorted(indexes, reverse=True)[len(members) // 2]
    if candidate < previous:
        raise QuorumWatermarkError("commit watermark regression")
    return candidate
