"""Read-only preflight of ledger journal entries; not durable recovery."""
from dataclasses import dataclass
from services.exchange.ledger_journal_codec import decode_ledger_command

class LedgerReplayPlanError(ValueError):
    """A journal snapshot cannot be safely planned for replay."""

@dataclass(frozen=True)
class PlannedLedgerCommand:
    sequence: int
    operation: str
    arguments: tuple

def plan_ledger_replay(entries, *, max_commands=100_000):
    """Validate a complete contiguous ledger snapshot before state replay.

    The caller must obtain entries from CommandJournal.entries(). This function
    does not authenticate journal data or check Ledger business state.
    """
    if type(max_commands) is not int or max_commands < 1:
        raise LedgerReplayPlanError("max_commands must be a positive integer")
    try:
        iterator = iter(entries)
    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        raise LedgerReplayPlanError("journal snapshot iterator initialization failed") from exc
    try:
        return _plan_entries(iterator, max_commands)
    except LedgerReplayPlanError:
        raise
    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        raise LedgerReplayPlanError("journal snapshot iteration failed") from exc

def _plan_entries(iterator, max_commands):
    planned = []
    for expected, entry in enumerate(iterator, 1):
        if expected > max_commands:
            raise LedgerReplayPlanError("journal snapshot exceeds max_commands")
        if type(entry) is not dict or set(entry) != {"sequence", "payload"}:
            raise LedgerReplayPlanError(f"invalid journal entry {expected}")
        if type(entry["sequence"]) is not int or entry["sequence"] != expected:
            raise LedgerReplayPlanError(f"noncontiguous sequence at entry {expected}")
        try:
            operation, arguments = decode_ledger_command(entry["payload"])
        except (ValueError, TypeError) as exc:
            raise LedgerReplayPlanError(f"invalid ledger command at entry {expected}") from exc
        planned.append(PlannedLedgerCommand(expected, operation, arguments))
    return tuple(planned)
