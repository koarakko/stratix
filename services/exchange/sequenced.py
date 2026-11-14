"""Atomic in-memory bridge between sequenced orders and deterministic matching.

Educational only: copying memory is NOT durable replication or writer fencing.
"""
from copy import deepcopy
from typing import Iterable

from services.exchange.lifecycle import OrderLifecycle, project_lifecycle
from services.matching.model import CancelRequest, Execution, LimitOrder, MatchingEngine
from services.orders.model import CancelOrder, Command, OrderStateMachine, PlaceOrder, SequenceError


class LifecycleConsistencyError(ValueError):
    """Projected lifecycle disagrees with the matching engine's open quantities."""


def _verified_lifecycle(orders: OrderStateMachine, matching: MatchingEngine) -> dict[str, OrderLifecycle]:
    """Project one logical snapshot, comparing independent remaining quantities."""
    history = orders.history()
    # Reconstruct executions from the exact committed command order; quantity
    # totals alone cannot detect forged makers, prices, or event ordering.
    actions = []
    for command in history:
        payload = command.payload
        if isinstance(payload, PlaceOrder):
            actions.append(LimitOrder(payload.order_id, payload.market, payload.side,
                                      payload.price, payload.quantity))
        elif isinstance(payload, CancelOrder):
            actions.append(CancelRequest(payload.order_id))
        else:
            raise LifecycleConsistencyError("unsupported committed command")
    expected = MatchingEngine.replay_actions(actions)
    if expected.executions() != matching.executions():
        raise LifecycleConsistencyError("executions disagree with committed command replay")
    lifecycle = project_lifecycle(history, matching.executions())
    for order_id, state in lifecycle.items():
        if state.remaining != matching.remaining(order_id) or state.remaining != expected.remaining(order_id):
            raise LifecycleConsistencyError(f"remaining quantity mismatch for {order_id}")
    return lifecycle


class SequencedExchange:
    def __init__(self) -> None:
        self._orders = OrderStateMachine()
        self._matching = MatchingEngine()

    def apply(self, command: Command) -> tuple[Execution, ...]:
        """Apply atomically; an identical committed retry produces no new fills."""
        orders = deepcopy(self._orders)
        matching = deepcopy(self._matching)
        if not orders.apply(command):
            # An idempotent acknowledgement must never hide a corrupted book.
            _verified_lifecycle(self._orders, self._matching)
            return ()
        payload = command.payload
        if isinstance(payload, PlaceOrder):
            fills = matching.submit(LimitOrder(payload.order_id, payload.market,
                                               payload.side, payload.price, payload.quantity))
        elif isinstance(payload, CancelOrder):
            matching.cancel(payload.order_id)
            fills = ()
        else:
            raise ValueError("unsupported command")
        # Validate both independently maintained representations before publishing.
        _verified_lifecycle(orders, matching)
        self._orders, self._matching = orders, matching
        return fills

    def history(self) -> tuple[Command, ...]:
        return self._orders.history()

    def executions(self) -> tuple[Execution, ...]:
        return self._matching.executions()

    def remaining(self, order_id: str):
        return self._matching.remaining(order_id)

    def lifecycle(self) -> dict[str, OrderLifecycle]:
        """Return a fresh, verified projection of all committed order states."""
        return _verified_lifecycle(self._orders, self._matching)

    @classmethod
    def replay(cls, commands: Iterable[Command]) -> "SequencedExchange":
        exchange = cls()
        for command in commands:
            if command.sequence <= len(exchange.history()):
                raise SequenceError("replay contains duplicate or out-of-order sequence")
            exchange.apply(command)
        return exchange
