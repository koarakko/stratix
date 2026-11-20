"""In-memory fencing decision gate; not a distributed lease or durable epoch store."""
from dataclasses import dataclass


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
        self._leader = None

    def install(self, token: LeadershipToken) -> None:
        if not isinstance(token, LeadershipToken):
            raise FencingError("invalid leadership token")
        if token.epoch <= self._minimum_epoch:
            raise FencingError("epoch not newer than durable high-water mark")
        if self._leader is not None and token.epoch <= self._leader.epoch:
            raise FencingError("stale or conflicting leadership epoch")
        self._leader = token

    def authorize(self, token: LeadershipToken) -> None:
        if not isinstance(token, LeadershipToken) or token != self._leader:
            raise FencingError("write denied: no matching active leader")

    def revoke(self) -> None:
        self._leader = None
