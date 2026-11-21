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
        "post": {"operation", "transaction_id", "postings"},
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
        if name == "postings":
            if type(value) is not list or len(value) < 2:
                raise LedgerCommandError("postings must be a list with at least two entries")
            normalized = []
            totals = {}
            for entry in value:
                if type(entry) is not dict or set(entry) != {"account", "asset", "amount"}:
                    raise LedgerCommandError("invalid posting fields")
                account, asset, amount = entry["account"], entry["asset"], entry["amount"]
                if any(type(v) is not str or not v.strip() for v in (account, asset)):
                    raise LedgerCommandError("invalid posting account or asset")
                if type(amount) is not int or amount == 0:
                    raise LedgerCommandError("posting amount must be a nonzero integer")
                totals[asset] = totals.get(asset, 0) + amount
                normalized.append((account, asset, amount))
            if any(totals.values()):
                raise LedgerCommandError("postings must balance per asset")
        elif name == "amount":
            if type(value) is not int or value <= 0:
                raise LedgerCommandError("amount must be a positive integer")
        elif type(value) is not str or not value.strip():
            raise LedgerCommandError(f"invalid {name}")
    if operation == "post":
        if command["transaction_id"].startswith(("reservation-settle:", "reservation-fill:")):
            raise LedgerCommandError("reserved transaction namespace")
        return operation, (("postings", tuple(normalized)), ("transaction_id", command["transaction_id"]))
    return operation, tuple((name, command[name]) for name in sorted(fields[operation] - {"operation"}))


def encode_ledger_command(operation, **fields):
    """Construct an isolated JSON-safe validated payload with a stable field schema."""
    payload = {"type": "ledger", "version": 1, "command": {"operation": operation, **fields}}
    op, normalized = decode_ledger_command(payload)
    values = dict(normalized)
    if op == "post":
        values["postings"] = [dict(account=a, asset=s, amount=n) for a, s, n in values["postings"]]
    return {"type": "ledger", "version": 1, "command": {"operation": op, **values}}
