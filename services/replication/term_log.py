"""Term-bound v2 hash chain; separate from legacy v1 entries."""
from dataclasses import dataclass
from hashlib import sha256

GENESIS = '0' * 64
DOMAIN = b'stratix-term-log-v2\x00'

class TermLogError(ValueError):
    pass

@dataclass(frozen=True)
class TermLogEntry:
    sequence: int
    term: int
    payload: bytes
    previous_hash: str
    entry_hash: str

def _uint(value, name, minimum):
    if type(value) is not int or not minimum <= value < 2**64:
        raise TermLogError(f'{name} must be uint64 >= {minimum}')

def _hash(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise TermLogError('invalid lowercase SHA-256 digest')

def _digest(sequence, term, payload, previous):
    return sha256(DOMAIN + sequence.to_bytes(8, 'big') + term.to_bytes(8, 'big')
                  + len(payload).to_bytes(8, 'big') + payload + bytes.fromhex(previous)).hexdigest()

def verify_term_log(entries):
    previous = GENESIS
    last_term = 0
    for expected, entry in enumerate(entries, 1):
        if type(entry) is not TermLogEntry:
            raise TermLogError('invalid term log entry')
        _uint(entry.sequence, 'sequence', 1)
        _uint(entry.term, 'term', 1)
        if entry.sequence != expected or entry.term < last_term:
            raise TermLogError('noncontiguous sequence or decreasing term')
        if type(entry.payload) is not bytes:
            raise TermLogError('payload must be bytes')
        _hash(entry.previous_hash)
        _hash(entry.entry_hash)
        if entry.previous_hash != previous or entry.entry_hash != _digest(entry.sequence, entry.term, entry.payload, previous):
            raise TermLogError('broken term-bound hash chain')
        previous, last_term = entry.entry_hash, entry.term
    return previous

def append_term(entries, term, payload):
    snapshot = tuple(entries)
    verify_term_log(snapshot)
    _uint(term, 'term', 1)
    if snapshot and term < snapshot[-1].term:
        raise TermLogError('term regression')
    if type(payload) is not bytes:
        raise TermLogError('payload must be bytes')
    sequence = len(snapshot) + 1
    _uint(sequence, 'sequence', 1)
    previous = snapshot[-1].entry_hash if snapshot else GENESIS
    return snapshot + (TermLogEntry(sequence, term, payload, previous, _digest(sequence, term, payload, previous)),)
