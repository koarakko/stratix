"""Strict, versioned order-command codec for the local educational journal.

Only decoding and read-only replay are supported; this module does not provide
transactional journal+matching commits or durable order acknowledgements.
"""
from decimal import Decimal, InvalidOperation

from services.exchange.command_log import CommandJournal, JournalError
from services.orders.model import CancelOrder, Command, OrderStateMachine, PlaceOrder


class CommandCodecError(JournalError):
    """Unknown schema, malformed command, or invalid replay."""


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise CommandCodecError("expected nonempty string")
    return value


def _decimal(value):
    if not isinstance(value, str):
        raise CommandCodecError("decimal must be encoded as a string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise CommandCodecError("invalid decimal") from exc
    if not number.is_finite() or number <= 0 or str(number) != value:
        raise CommandCodecError("decimal must be positive finite and canonical")
    return number


def encode_command(command: Command) -> dict:
    """Encode a supported command using a stable version-1 JSON schema."""
    if not isinstance(command, Command) or type(command.sequence) is not int or command.sequence < 1:
        raise CommandCodecError("invalid command sequence")
    payload = command.payload
    if isinstance(payload, PlaceOrder):
        if payload.side not in ("buy", "sell"):
            raise CommandCodecError("invalid side")
        result = {"version": 1, "type": "place", "order_id": _text(payload.order_id),
                  "account": _text(payload.account), "market": _text(payload.market),
                  "side": payload.side, "price": str(payload.price),
                  "quantity": str(payload.quantity)}
        _decimal(result["price"])
        _decimal(result["quantity"])
        return result
    if isinstance(payload, CancelOrder):
        return {"version": 1, "type": "cancel", "order_id": _text(payload.order_id)}
    raise CommandCodecError("unsupported command type")


def decode_command(sequence: int, payload: dict) -> Command:
    """Reject unknown fields and noncanonical values instead of guessing."""
    if type(sequence) is not int or sequence < 1 or not isinstance(payload, dict):
        raise CommandCodecError("invalid command envelope")
    kind = payload.get("type")
    if type(payload.get("version")) is not int or payload["version"] != 1:
        raise CommandCodecError("unsupported command schema version")
    if kind == "place":
        if set(payload) != {"version", "type", "order_id", "account", "market", "side", "price", "quantity"}:
            raise CommandCodecError("unexpected placement fields")
        if payload["side"] not in ("buy", "sell"):
            raise CommandCodecError("invalid side")
        command = Command(sequence, PlaceOrder(_text(payload["order_id"]), _text(payload["account"]),
                          _text(payload["market"]), payload["side"], _decimal(payload["price"]),
                          _decimal(payload["quantity"])))
    elif kind == "cancel":
        if set(payload) != {"version", "type", "order_id"}:
            raise CommandCodecError("unexpected cancellation fields")
        command = Command(sequence, CancelOrder(_text(payload["order_id"])))
    else:
        raise CommandCodecError("unknown command type")
    if encode_command(command) != payload:
        raise CommandCodecError("noncanonical command")
    return command


def recover_order_state(journal: CommandJournal) -> OrderStateMachine:
    """Read-only, fail-closed replay of a checked journal into order state.

    Re-reads disk to detect corruption after journal initialization. Never
    returns a partially recovered state or silently truncates a bad record.
    """
    commands = []
    try:
        for entry in journal.read_all():
            commands.append(decode_command(entry["sequence"], entry["payload"]))
        return OrderStateMachine.replay(commands)
    except (ValueError, TypeError, AttributeError) as exc:
        raise CommandCodecError("journal order replay rejected") from exc


def recover_exchange(journal: CommandJournal):
    """Read-only, fail-closed reconstruction of orders, fills and remaining book.

    No journal writes, acknowledgement, quorum commitment or writer fencing.
    """
    from services.exchange.sequenced import SequencedExchange

    try:
        commands = [decode_command(entry["sequence"], entry["payload"])
                    for entry in journal.read_all()]
        exchange = SequencedExchange.replay(commands)
        exchange.lifecycle()  # Verify even the empty snapshot before publishing.
        return exchange
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise CommandCodecError("journal exchange replay rejected") from exc
