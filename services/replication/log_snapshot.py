"""Bounded materialization for untrusted in-memory leader-log iterables."""

DEFAULT_MAX_LOG_SNAPSHOT_ENTRIES = 100_000
DEFAULT_MAX_LOG_SNAPSHOT_PAYLOAD_BYTES = 64 * 1024 * 1024


class LogSnapshotLimitError(ValueError):
    """The supplied log snapshot exceeds a configured resource limit."""


def materialize_log_snapshot(
    entries,
    *,
    max_entries=DEFAULT_MAX_LOG_SNAPSHOT_ENTRIES,
    max_payload_bytes=DEFAULT_MAX_LOG_SNAPSHOT_PAYLOAD_BYTES,
):
    """Materialize a complete snapshot within entry-count and payload-byte caps.

    One additional item is read to distinguish an exactly-at-limit iterable
    from an oversized one. That lookahead item is discarded and no partial
    snapshot is returned on overflow. bytes-valued payloads are included in
    the aggregate byte budget; malformed payload types are left for the
    version-specific verifier to reject. Ordinary iterator exceptions
    propagate to the wrapper for normalization, while process-control
    BaseException subclasses are never swallowed.
    """
    if type(max_entries) is not int or max_entries < 0:
        raise ValueError("max_entries must be a nonnegative exact integer")
    if type(max_payload_bytes) is not int or max_payload_bytes < 0:
        raise ValueError("max_payload_bytes must be a nonnegative exact integer")

    iterator = iter(entries)
    snapshot = []
    payload_bytes = 0
    for _ in range(max_entries):
        try:
            entry = next(iterator)
        except StopIteration:
            return tuple(snapshot)
        payload = getattr(entry, "payload", None)
        if isinstance(payload, bytes):
            payload_bytes += len(payload)
            if payload_bytes > max_payload_bytes:
                raise LogSnapshotLimitError(
                    f"log snapshot payload exceeds configured limit of {max_payload_bytes} bytes"
                )
        snapshot.append(entry)

    try:
        next(iterator)
    except StopIteration:
        return tuple(snapshot)
    raise LogSnapshotLimitError(
        f"log snapshot exceeds configured limit of {max_entries} entries"
    )
