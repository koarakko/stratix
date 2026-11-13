"""Deterministic educational order command model; NOT a matching engine.

Single-writer, in-memory only. No durable acknowledgements or funds safety.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

@dataclass(frozen=True)
class PlaceOrder:
    order_id: str
    account: str
    market: str
    side: str
    price: Decimal
    quantity: Decimal

@dataclass(frozen=True)
class CancelOrder:
    order_id: str

@dataclass(frozen=True)
class Command:
    sequence: int
    payload: PlaceOrder | CancelOrder

@dataclass(frozen=True)
class Order:
    request: PlaceOrder
    status: str

class SequenceError(ValueError):
    """Missing or conflicting sequence."""

class OrderError(ValueError):
    """Invalid order identity or lifecycle."""

class OrderStateMachine:
    def __init__(self) -> None:
        self._history: list[Command] = []
        self._orders: dict[str, Order] = {}

    def apply(self, command: Command) -> bool:
        """Apply a contiguous command; identical committed retries return False."""
        if not isinstance(command.sequence, int) or isinstance(command.sequence, bool):
            raise SequenceError("sequence must be an integer")
        if 1 <= command.sequence <= len(self._history):
            if self._history[command.sequence - 1] == command:
                return False
            raise SequenceError("conflicting command at committed sequence")
        if command.sequence != len(self._history) + 1:
            raise SequenceError("sequence must be contiguous starting at 1")

        payload = command.payload
        if isinstance(payload, PlaceOrder):
            if not all((payload.order_id.strip(), payload.account.strip(), payload.market.strip())):
                raise OrderError("order_id, account and market must be nonempty")
            if payload.side not in ("buy", "sell"):
                raise OrderError("side must be buy or sell")
            if any(not isinstance(v, Decimal) or not v.is_finite() or v <= 0
                   for v in (payload.price, payload.quantity)):
                raise OrderError("price and quantity must be positive finite Decimals")
            if payload.order_id in self._orders:
                raise OrderError("order_id cannot be reused")
            self._orders[payload.order_id] = Order(payload, "open")
        elif isinstance(payload, CancelOrder):
            current = self._orders.get(payload.order_id)
            if current is None or current.status != "open":
                raise OrderError("only an existing open order may be cancelled")
            self._orders[payload.order_id] = Order(current.request, "cancelled")
        else:
            raise OrderError("unsupported command type")
        self._history.append(command)
        return True

    def order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def history(self) -> tuple[Command, ...]:
        return tuple(self._history)

    @classmethod
    def replay(cls, commands: Iterable[Command]) -> "OrderStateMachine":
        state = cls()
        for command in commands:
            if not state.apply(command):
                raise SequenceError("replay contains duplicate sequence")
        return state
