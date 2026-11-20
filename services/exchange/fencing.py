"""In-memory fencing decision gate; not a distributed lease or durable epoch store."""
from dataclasses import dataclass
from threading import RLock


class FencingError(ValueError):
    """A command is not authorized for the current leadership epoch."""


@dataclass(frozen=True)
class LeadershipToken:
    epoch: int
    holder: str

    def __post_init__(self):
        if type(self.epoch) is not int or self.epoch < 1:
            raise FencingError("epoch must be a positive integer")
        if not isinstance(self.holder, str) or not self.holder.strip():
            raise FencingError("holder must be nonempty")


class FencingGate:
    """Fail closed on stale or conflicting leadership; local-process demonstration only.

    Epochs must come from an external linearizable authority. After restart,
    restore a trusted durable high-water mark before authorizing any writes.
    """

    def __init__(self, minimum_epoch: int):
        if type(minimum_epoch) is not int or minimum_epoch < 0:
            raise FencingError("minimum epoch must be a nonnegative integer")
        self._minimum_epoch = minimum_epoch
        self._highest_epoch = minimum_epoch
        self._leader = None
        self._lock = RLock()
        self._operation_active = False

    def install(self, token: LeadershipToken) -> None:
        with self._lock:
            if self._operation_active:
                raise FencingError("cannot change leadership inside authorized operation")
            if not isinstance(token, LeadershipToken):
                raise FencingError("invalid leadership token")
            if token.epoch <= self._highest_epoch:
                raise FencingError("stale or previously used leadership epoch")
            self._highest_epoch = token.epoch
            self._leader = token

    def authorize(self, token: LeadershipToken) -> None:
        with self._lock:
            if not isinstance(token, LeadershipToken) or token != self._leader:
                raise FencingError("write denied: no matching active leader")

    def run_authorized(self, token: LeadershipToken, operation, *args, **kwargs):
        """Serialize local leadership changes with one operation; not distributed fencing."""
        with self._lock:
            self.authorize(token)
            if self._operation_active:
                raise FencingError("nested authorized operation is forbidden")
            self._operation_active = True
            try:
                return operation(*args, **kwargs)
            finally:
                self._operation_active = False

    def revoke(self) -> None:
        with self._lock:
            if self._operation_active:
                raise FencingError("cannot revoke leadership inside authorized operation")
            self._leader = None
