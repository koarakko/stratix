"""Pure lifecycle projection from committed commands and execution events.

Educational only; callers must supply a consistent, sequenced snapshot.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from services.orders.model import CancelOrder, Command, PlaceOrder
from services.matching.model import Execution


@dataclass(frozen=True)
class OrderLifecycle:
    status: str
    quantity: Decimal
    filled: Decimal
    remaining: Decimal
    cancelled: Decimal


def project_lifecycle(commands: Iterable[Command], executions: Iterable[Execution]) -> dict[str, OrderLifecycle]:
    """Derive immutable order states without interpreting zero remainder as cancellation."""
    placed: dict[str, PlaceOrder] = {}
    cancelled: set[str] = set()
    for command in commands:
        if isinstance(command.payload, PlaceOrder):
            if command.payload.order_id in placed:
                raise ValueError("duplicate placement")
            placed[command.payload.order_id] = command.payload
        elif isinstance(command.payload, CancelOrder):
            if command.payload.order_id not in placed or command.payload.order_id in cancelled:
                raise ValueError("invalid cancellation")
            cancelled.add(command.payload.order_id)
        else:
            raise ValueError("unsupported command")
    filled = {oid: Decimal(0) for oid in placed}
    for execution in executions:
        if execution.maker_order_id not in placed or execution.taker_order_id not in placed:
            raise ValueError("execution references unknown order")
        if not isinstance(execution.quantity, Decimal) or not execution.quantity.is_finite() or execution.quantity <= 0:
            raise ValueError("invalid execution quantity")
        for oid in (execution.maker_order_id, execution.taker_order_id):
            filled[oid] += execution.quantity
            if filled[oid] > placed[oid].quantity:
                raise ValueError("overfilled order")
    result = {}
    for oid, request in placed.items():
        open_qty = request.quantity - filled[oid]
        is_cancelled = oid in cancelled
        if is_cancelled and open_qty == 0:
            raise ValueError("fully filled order cannot be cancelled")
        result[oid] = OrderLifecycle(
            "cancelled" if is_cancelled else "filled" if open_qty == 0 else
            "partially_filled" if filled[oid] > 0 else "open",
            request.quantity, filled[oid], Decimal(0) if is_cancelled else open_qty,
            open_qty if is_cancelled else Decimal(0))
    return result
