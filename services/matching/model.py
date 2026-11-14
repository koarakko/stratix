"""Deterministic, single-writer in-memory limit order matcher (educational only)."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class LimitOrder:
    order_id: str
    market: str
    side: str
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True)
class CancelRequest:
    order_id: str


@dataclass(frozen=True)
class Execution:
    execution_id: str
    maker_order_id: str
    taker_order_id: str
    market: str
    price: Decimal
    quantity: Decimal


class MatchingError(ValueError):
    """Invalid order or duplicate order identity."""


class MatchingEngine:
    def __init__(self) -> None:
        self._orders: dict[str, LimitOrder] = {}
        self._remaining: dict[str, Decimal] = {}
        self._executions: list[Execution] = []
        self._sequence = 0

    def submit(self, order: LimitOrder) -> tuple[Execution, ...]:
        """Match at resting-maker price; insertion order breaks price ties."""
        if not isinstance(order, LimitOrder):
            raise MatchingError("expected LimitOrder")
        if not all(isinstance(v, str) and v.strip() for v in (order.order_id, order.market)):
            raise MatchingError("order_id and market must be nonempty strings")
        if order.side not in ("buy", "sell"):
            raise MatchingError("side must be buy or sell")
        if any(not isinstance(v, Decimal) or not v.is_finite() or v <= 0
               for v in (order.price, order.quantity)):
            raise MatchingError("price and quantity must be positive finite Decimals")
        if order.order_id in self._orders:
            raise MatchingError("duplicate order_id")

        # Every validation happens before mutation. Single-writer execution only.
        self._orders[order.order_id] = order
        left = order.quantity
        opposite = "sell" if order.side == "buy" else "buy"
        candidates = [o for o in self._orders.values()
                      if o.order_id != order.order_id and o.market == order.market
                      and o.side == opposite and self._remaining.get(o.order_id, Decimal(0)) > 0
                      and (o.price <= order.price if order.side == "buy" else o.price >= order.price)]
        # Stable sort preserves insertion time for equal prices.
        candidates.sort(key=lambda o: o.price, reverse=order.side == "sell")
        produced: list[Execution] = []
        for maker in candidates:
            if left == 0:
                break
            qty = min(left, self._remaining[maker.order_id])
            self._sequence += 1
            event = Execution(f"exec-{self._sequence}", maker.order_id, order.order_id,
                              order.market, maker.price, qty)
            produced.append(event)
            self._executions.append(event)
            self._remaining[maker.order_id] -= qty
            left -= qty
        self._remaining[order.order_id] = left
        return tuple(produced)

    def cancel(self, order_id: str) -> Decimal:
        """Cancel an open remainder; return quantity removed from the book.

        Unknown, already filled, or already cancelled orders are rejected.
        Historical execution events are never modified.
        """
        if not isinstance(order_id, str) or not order_id.strip():
            raise MatchingError("order_id must be a nonempty string")
        if order_id not in self._orders or self._remaining[order_id] == 0:
            raise MatchingError("only an order with open remainder can be cancelled")
        removed = self._remaining[order_id]
        self._remaining[order_id] = Decimal(0)
        return removed

    def remaining(self, order_id: str) -> Decimal:
        return self._remaining[order_id]

    def executions(self) -> tuple[Execution, ...]:
        return tuple(self._executions)

    @classmethod
    def replay(cls, orders: Iterable[LimitOrder]) -> "MatchingEngine":
        engine = cls()
        for order in orders:
            engine.submit(order)
        return engine

    @classmethod
    def replay_actions(cls, actions: Iterable[LimitOrder | CancelRequest]) -> "MatchingEngine":
        """Replay a single-writer stream including cancellation commands."""
        engine = cls()
        for action in actions:
            if isinstance(action, LimitOrder):
                engine.submit(action)
            elif isinstance(action, CancelRequest):
                engine.cancel(action.order_id)
            else:
                raise MatchingError("unsupported replay action")
        return engine
