"""Fail-closed local append-only command journal; educational, single-writer only.

This journal is not a replicated commit log. A successful fsync does not imply
quorum commitment, and no leader fencing or crash-safe directory sync exists.
"""
import hashlib
import json
import os
import stat
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
            if not hasattr(os, "O_NOFOLLOW"):
                raise JournalError("symlink-safe journal opening is unsupported")
            try:
                fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
            except FileNotFoundError as exc:
                if self._observed_file or getattr(self, "_entries", ()):
                    raise JournalError("previously observed journal is missing") from exc
                return ()
            try:
                handle = os.fdopen(fd, "rb")
            except OSError as exc:
                # fdopen failed before taking ownership of the raw descriptor.
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise JournalError("journal read descriptor wrapping failed") from exc
            with handle:
                opened = os.fstat(handle.fileno())
                if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                    raise JournalError("journal must be a regular file with one hard link")
                identity = (opened.st_dev, opened.st_ino)
                if self._file_identity is not None and identity != self._file_identity:
                    raise JournalError("journal file identity changed")
                raw = handle.read()
                current = self.path.lstat()
                if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1 or identity != (current.st_dev, current.st_ino):
                    raise JournalError("journal replaced during read")
        except OSError as exc:
            raise JournalError("journal read failed after open or unsafe path") from exc
        if raw and not raw.endswith(b"\n"):
            raise JournalError("incomplete trailing record; manual recovery required")
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
        # Commit verified metadata only after every record and history check.
        self._observed_file = True
        self._file_identity = identity
        self._verified_size = len(raw)
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
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        except OSError as exc:
            raise JournalError("cannot safely open journal lock file") from exc
        try:
            try:
                handle = os.fdopen(fd, "r+b")
            except OSError as exc:
                # fdopen did not transfer descriptor ownership on failure.
                # A leaked descriptor could keep a lock alive unexpectedly.
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise JournalError("journal lock file descriptor wrapping failed") from exc
            with handle:
                try:
                    opened = os.fstat(handle.fileno())
                    if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                        raise JournalError("journal lock file must be regular with exactly one hard link")
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    try:
                        locked = os.fstat(handle.fileno())
                        try:
                            current = lock_path.lstat()
                        except FileNotFoundError as exc:
                            raise JournalError("lock file identity changed") from exc
                        if not stat.S_ISREG(current.st_mode) or (locked.st_dev, locked.st_ino) != (current.st_dev, current.st_ino):
                            raise JournalError("lock file identity changed")
                        if locked.st_nlink != 1 or current.st_nlink != 1:
                            raise JournalError("journal lock file has multiple hard links")
                        yield
                    finally:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError as exc:
                    raise JournalError("journal lock operation failed; reconcile before retry") from exc
        except OSError as exc:
            raise JournalError("journal lock file close failed; reconcile before retry") from exc

    def append(self, sequence: int, payload: dict) -> bool:
        if self._poisoned:
            raise JournalError("journal is poisoned after an I/O failure")
        try:
            with self._writer_lock():
                return self._append_locked(sequence, payload)
        except JournalError as exc:
            if "journal lock" in str(exc) or "lock file" in str(exc):
                self._poisoned = True
            raise

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
            if not hasattr(os, "O_NOFOLLOW"):
                raise JournalError("symlink-safe journal opening is unsupported")
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            except OSError as exc:
                raise JournalError("cannot safely open journal for append") from exc
            try:
                opened = os.fstat(fd)
                if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                    raise JournalError("journal must be a regular file with one hard link before write")
                if self._file_identity is not None and (opened.st_dev, opened.st_ino) != self._file_identity:
                    raise JournalError("journal file identity changed before write")
                current = self.path.lstat()
                if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
                    raise JournalError("journal path must be a regular file with one hard link before write")
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
        # Cache the serialized committed value, not the caller-owned mutable dict.
        self._entries += (json.loads(record)["data"],)
        return True

    def entries(self) -> tuple[dict, ...]:
        """Return only a disk-verified snapshot, never stale cached records."""
        return self.read_all()
