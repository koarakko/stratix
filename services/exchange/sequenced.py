"""Atomic in-memory bridge between sequenced orders and deterministic matching.

Educational only: copying memory is NOT durable replication or writer fencing.
"""
from copy import deepcopy
from typing import Iterable

from services.matching.model import Execution, LimitOrder, MatchingEngine
from services.orders.model import CancelOrder, Command, OrderStateMachine, PlaceOrder, SequenceError


class SequencedExchange:
    def __init__(self) -> None:
        self._orders = OrderStateMachine()
        self._matching = MatchingEngine()

    def apply(self, command: Command) -> tuple[Execution, ...]:
        """Apply atomically; an identical committed retry produces no new fills."""
        orders = deepcopy(self._orders)
        matching = deepcopy(self._matching)
        if not orders.apply(command):
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
        self._orders, self._matching = orders, matching
        return fills

    def history(self) -> tuple[Command, ...]:
        return self._orders.history()

    def executions(self) -> tuple[Execution, ...]:
        return self._matching.executions()

    def remaining(self, order_id: str):
        return self._matching.remaining(order_id)

    @classmethod
    def replay(cls, commands: Iterable[Command]) -> "SequencedExchange":
        exchange = cls()
        for command in commands:
            if command.sequence <= len(exchange.history()):
                raise SequenceError("replay contains duplicate or out-of-order sequence")
            exchange.apply(command)
        return exchange
