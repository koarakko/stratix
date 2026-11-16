"""Fail-closed local append-only command journal; educational, single-writer only.

This journal is not a replicated commit log. A successful fsync does not imply
quorum commitment, and no leader fencing or crash-safe directory sync exists.
"""
import hashlib
import json
import os
import fcntl
from contextlib import contextmanager
from pathlib import Path


class JournalError(ValueError):
    """Invalid or corrupted journal, including an incomplete final record."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _record(sequence: int, payload: dict) -> bytes:
    data = {"sequence": sequence, "payload": payload}
    digest = hashlib.sha256(_canonical(data)).hexdigest()
    return _canonical({"data": data, "sha256": digest}) + b"\n"


class CommandJournal:
    """Durable-ish single-process journal with strict sequence and retry checks.

    On an I/O error, the instance is poisoned; reopen only after diagnosing the
    file. This prevents a short/partial write from being silently overwritten.
    """

    def __init__(self, path):
        self.path = Path(path)
        self._poisoned = False
        self._observed_file = self.path.exists()
        self._file_identity = None
        self._verified_size = 0
        self._entries = self.read_all()

    def read_all(self) -> tuple[dict, ...]:
        try:
            with self.path.open("rb") as handle:
                identity = (os.fstat(handle.fileno()).st_dev, os.fstat(handle.fileno()).st_ino)
                if self._file_identity is not None and identity != self._file_identity:
                    raise JournalError("journal file identity changed")
                raw = handle.read()
                current = self.path.stat()
                if identity != (current.st_dev, current.st_ino):
                    raise JournalError("journal replaced during read")
        except FileNotFoundError as exc:
            if self._observed_file or getattr(self, "_entries", ()):
                raise JournalError("previously observed journal is missing") from exc
            return ()
        if raw and not raw.endswith(b"\n"):
            raise JournalError("incomplete trailing record; manual recovery required")
        self._observed_file = True
        self._file_identity = identity
        self._verified_size = len(raw)
        entries = []
        for line in raw.splitlines():
            try:
                outer = json.loads(line)
                if not isinstance(outer, dict) or set(outer) != {"data", "sha256"}:
                    raise ValueError("unexpected envelope")
                data = outer["data"]
                if not isinstance(data, dict) or set(data) != {"sequence", "payload"}:
                    raise ValueError("unexpected data")
                seq = data["sequence"]
                if type(seq) is not int or seq != len(entries) + 1 or not isinstance(data["payload"], dict):
                    raise ValueError("invalid sequence or payload")
                if not isinstance(outer["sha256"], str) or hashlib.sha256(_canonical(data)).hexdigest() != outer["sha256"]:
                    raise ValueError("checksum mismatch")
                if _record(seq, data["payload"]) != line + b"\n":
                    raise ValueError("noncanonical record")
            except (ValueError, TypeError, UnicodeError, KeyError) as exc:
                raise JournalError(f"invalid journal record {len(entries) + 1}") from exc
            entries.append(data)
        result = tuple(entries)
        if hasattr(self, "_entries") and result != self._entries:
            raise JournalError("journal changed since initialization")
        return result

    @contextmanager
    def _writer_lock(self):
        # Stable sidecar inode avoids locking a journal inode that can be replaced.
        lock_path = self.path.with_name(self.path.name + ".lock")
        # Refuse symlinks: following a substituted sidecar can lock an unrelated
        # inode and can create competing lock domains across cooperating writers.
        if not hasattr(os, "O_NOFOLLOW"):
            raise JournalError("symlink-safe sidecar opening is unsupported")
        try:
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        except OSError as exc:
            raise JournalError("cannot safely open journal lock file") from exc
        with os.fdopen(fd, "r+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                locked = os.fstat(handle.fileno())
                try:
                    current = lock_path.stat()
                except FileNotFoundError as exc:
                    raise JournalError("lock file identity changed") from exc
                if (locked.st_dev, locked.st_ino) != (current.st_dev, current.st_ino):
                    raise JournalError("lock file identity changed")
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def append(self, sequence: int, payload: dict) -> bool:
        with self._writer_lock():
            return self._append_locked(sequence, payload)

    def _append_locked(self, sequence: int, payload: dict) -> bool:
        """Return False for identical retry; reject conflicting/gapped sequences."""
        if self._poisoned:
            raise JournalError("journal is poisoned after an I/O failure")
        # Detect external edits before accepting retries or extending the file.
        self.read_all()
        if type(sequence) is not int or not isinstance(payload, dict):
            raise JournalError("sequence must be int and payload must be dict")
        try:
            record = _record(sequence, payload)
        except (ValueError, TypeError) as exc:
            raise JournalError("payload must be JSON serializable") from exc
        if 1 <= sequence <= len(self._entries):
            if self._entries[sequence - 1] == {"sequence": sequence, "payload": payload}:
                return False
            raise JournalError("conflicting committed sequence")
        if sequence != len(self._entries) + 1:
            raise JournalError("sequence gap")
        # O_APPEND prevents offset reuse, but NOT multiple-writer coordination.
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                opened = os.fstat(fd)
                if self._file_identity is not None and (opened.st_dev, opened.st_ino) != self._file_identity:
                    raise JournalError("journal file identity changed before write")
                current = self.path.stat()
                if opened.st_size != self._verified_size or current.st_size != self._verified_size:
                    raise JournalError("journal size changed before write")
                if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                    raise JournalError("journal replaced before write")
                written = os.write(fd, record)
                if written != len(record):
                    raise OSError("short journal write")
                os.fsync(fd)
            finally:
                os.close(fd)
        except (OSError, JournalError):
            self._poisoned = True
            raise
        self._observed_file = True
        self._file_identity = (opened.st_dev, opened.st_ino)
        self._verified_size += len(record)
        self._entries += ({"sequence": sequence, "payload": payload},)
        return True

    def entries(self) -> tuple[dict, ...]:
        """Return only a disk-verified snapshot, never stale cached records."""
        return self.read_all()
