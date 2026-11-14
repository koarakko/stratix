"""Hash-linked committed command log integrity checks (educational, not consensus)."""
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

GENESIS = "0" * 64
DOMAIN = b"stratix-log-v1\x00"


class LogIntegrityError(ValueError):
    """A log entry, its ordering, or its hash chain is invalid."""


@dataclass(frozen=True)
class LogEntry:
    sequence: int
    payload: bytes
    previous_hash: str
    entry_hash: str


def _digest(sequence: int, payload: bytes, previous_hash: str) -> str:
    # Length prefix makes the byte encoding unambiguous.
    return sha256(DOMAIN + sequence.to_bytes(8, "big")
                  + len(payload).to_bytes(8, "big") + payload
                  + bytes.fromhex(previous_hash)).hexdigest()


def _check_sequence(sequence: int) -> None:
    if type(sequence) is not int or not 1 <= sequence < 2**64:
        raise LogIntegrityError("sequence must be a positive uint64")


def _check_hash(value: str) -> None:
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise LogIntegrityError("hash must be 64 lowercase hexadecimal characters")


def append(entries: Iterable[LogEntry], payload: bytes) -> tuple[LogEntry, ...]:
    """Return a new verified log with one appended payload; never mutate the input."""
    existing = tuple(entries)
    verify(existing)
    if not isinstance(payload, bytes):
        raise LogIntegrityError("payload must be immutable bytes")
    sequence = len(existing) + 1
    _check_sequence(sequence)
    previous = existing[-1].entry_hash if existing else GENESIS
    entry = LogEntry(sequence, payload, previous, _digest(sequence, payload, previous))
    return existing + (entry,)


def verify(entries: Iterable[LogEntry]) -> str:
    """Verify contiguous ordering and hash links; return the final hash."""
    previous = GENESIS
    for expected, entry in enumerate(entries, 1):
        if not isinstance(entry, LogEntry):
            raise LogIntegrityError("expected LogEntry")
        _check_sequence(entry.sequence)
        if entry.sequence != expected:
            raise LogIntegrityError("noncontiguous or duplicate sequence")
        if not isinstance(entry.payload, bytes):
            raise LogIntegrityError("payload must be immutable bytes")
        _check_hash(entry.previous_hash)
        _check_hash(entry.entry_hash)
        if entry.previous_hash != previous:
            raise LogIntegrityError("broken previous-hash link")
        if entry.entry_hash != _digest(entry.sequence, entry.payload, previous):
            raise LogIntegrityError("entry digest mismatch")
        previous = entry.entry_hash
    return previous
