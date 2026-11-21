"""Strict, versioned ledger command payload codec (not a durable writer)."""


class LedgerCommandError(ValueError):
    """Reject malformed or unsupported ledger commands before replay."""


def decode_ledger_command(payload):
    """Return a normalized immutable command; reject ambiguous JSON values."""
    if not isinstance(payload, dict) or set(payload) != {"type", "version", "command"}:
        raise LedgerCommandError("invalid ledger envelope")
    if payload["type"] != "ledger" or type(payload["version"]) is not int or payload["version"] != 1:
        raise LedgerCommandError("unsupported ledger command version")
    command = payload["command"]
    if not isinstance(command, dict) or "operation" not in command:
        raise LedgerCommandError("invalid command")
    operation = command["operation"]
    fields = {
        "reserve": {"operation", "reservation_id", "account", "asset", "amount"},
        "release": {"operation", "reservation_id"},
        "settle": {"operation", "reservation_id", "destination"},
        "settle_partial": {"operation", "reservation_id", "destination", "amount", "fill_id"},
    }
    if type(operation) is not str or operation not in fields or set(command) != fields[operation]:
        raise LedgerCommandError("unsupported operation or fields")
    for name, value in command.items():
        if name == "operation":
            continue
        if name == "amount":
            if type(value) is not int or value <= 0:
                raise LedgerCommandError("amount must be a positive integer")
        elif type(value) is not str or not value.strip():
            raise LedgerCommandError(f"invalid {name}")
    return operation, tuple((name, command[name]) for name in sorted(fields[operation] - {"operation"}))


def encode_ledger_command(operation, **fields):
    """Construct a JSON-safe validated payload with a stable field schema."""
    payload = {"type": "ledger", "version": 1, "command": {"operation": operation, **fields}}
    decode_ledger_command(payload)
    return payload
