"""Independent safety checks for sequenced execution events (educational only)."""
from decimal import Decimal
from typing import Iterable

from services.matching.model import Execution
from services.orders.model import CancelOrder, Command, PlaceOrder


class ExecutionInvariantError(ValueError):
    """An execution violates basic order, price, or quantity invariants."""


def verify_execution_invariants(commands: Iterable[Command], executions: Iterable[Execution]) -> None:
    """Check causal and economic constraints without invoking the matching engine.

    Events are grouped by their taker placement in the sequenced command stream.
    This does not prove that every eligible match happened or that best-price
    priority was respected; the replay oracle checks exact event reproduction.
    """
    events = iter(executions)
    event = next(events, None)
    orders: dict[str, PlaceOrder] = {}
    remaining: dict[str, Decimal] = {}
    seen_ids: set[str] = set()

    for command in commands:
        payload = command.payload
        if isinstance(payload, PlaceOrder):
            if payload.order_id in orders:
                raise ExecutionInvariantError("duplicate placement")
            if payload.side not in ("buy", "sell") or any(
                not isinstance(v, Decimal) or not v.is_finite() or v <= 0
                for v in (payload.price, payload.quantity)
            ):
                raise ExecutionInvariantError("invalid placed order")
            orders[payload.order_id] = payload
            remaining[payload.order_id] = payload.quantity
            while event is not None and event.taker_order_id == payload.order_id:
                maker = orders.get(event.maker_order_id)
                if maker is None or maker.order_id == payload.order_id:
                    raise ExecutionInvariantError("maker must be a prior, distinct order")
                if (not isinstance(event.execution_id, str) or not event.execution_id.strip()
                        or event.execution_id in seen_ids):
                    raise ExecutionInvariantError("invalid or duplicate execution ID")
                seen_ids.add(event.execution_id)
                if (not isinstance(event.quantity, Decimal) or not event.quantity.is_finite()
                        or event.quantity <= 0):
                    raise ExecutionInvariantError("invalid execution quantity")
                if (not isinstance(event.price, Decimal) or not event.price.is_finite()
                        or event.price <= 0):
                    raise ExecutionInvariantError("invalid execution price")
                if (maker.market != payload.market or event.market != payload.market
                        or maker.side == payload.side):
                    raise ExecutionInvariantError("execution market or side mismatch")
                if event.price != maker.price:
                    raise ExecutionInvariantError("execution must use maker price")
                if ((payload.side == "buy" and event.price > payload.price)
                        or (payload.side == "sell" and event.price < payload.price)):
                    raise ExecutionInvariantError("execution exceeds taker limit")
                if event.quantity > remaining[maker.order_id] or event.quantity > remaining[payload.order_id]:
                    raise ExecutionInvariantError("execution exceeds open quantity")
                remaining[maker.order_id] -= event.quantity
                remaining[payload.order_id] -= event.quantity
                event = next(events, None)
        elif isinstance(payload, CancelOrder):
            if payload.order_id not in remaining or remaining[payload.order_id] <= 0:
                raise ExecutionInvariantError("cancel without open quantity")
            remaining[payload.order_id] = Decimal(0)
        else:
            raise ExecutionInvariantError("unsupported command")
    if event is not None:
        raise ExecutionInvariantError("execution not attributable to its taker placement")
