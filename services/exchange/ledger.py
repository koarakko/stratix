"""In-memory double-entry ledger reference; not durable or production-safe."""
from dataclasses import dataclass
from threading import RLock


class LedgerError(ValueError):
    """Invalid or conflicting ledger transaction."""


@dataclass(frozen=True)
class Posting:
    account: str
    asset: str
    amount: int

    def __post_init__(self):
        if not isinstance(self.account, str) or not self.account.strip():
            raise LedgerError("account must be nonempty")
        if not isinstance(self.asset, str) or not self.asset.strip():
            raise LedgerError("asset must be nonempty")
        if type(self.amount) is not int or self.amount == 0:
            raise LedgerError("amount must be a nonzero integer")


class Ledger:
    """Atomic in-process balanced postings, with transaction-id idempotency."""

    def __init__(self, protected_accounts=()):
        try:
            accounts = frozenset(protected_accounts)
        except TypeError as exc:
            raise LedgerError("protected_accounts must be iterable and hashable") from exc
        if any(not isinstance(a, str) or not a.strip() for a in accounts):
            raise LedgerError("protected_accounts must contain nonempty account names")
        self._protected_accounts = accounts
        self._balances = {}
        self._transactions = {}
        self._lock = RLock()

    def post(self, transaction_id: str, postings) -> bool:
        if not isinstance(transaction_id, str) or not transaction_id.strip():
            raise LedgerError("transaction id must be nonempty")
        try:
            entries = tuple(postings)
        except TypeError as exc:
            raise LedgerError("postings must be iterable") from exc
        if len(entries) < 2 or any(not isinstance(p, Posting) for p in entries):
            raise LedgerError("at least two valid postings required")
        totals = {}
        for p in entries:
            totals[p.asset] = totals.get(p.asset, 0) + p.amount
        if any(totals.values()):
            raise LedgerError("postings must balance per asset")
        with self._lock:
            previous = self._transactions.get(transaction_id)
            if previous is not None:
                if previous == entries:
                    return False
                raise LedgerError("conflicting transaction id")
            updated = self._balances.copy()
            for p in entries:
                key = (p.account, p.asset)
                updated[key] = updated.get(key, 0) + p.amount
            if any(amount < 0 for (account, _), amount in updated.items()
                   if account in self._protected_accounts):
                raise LedgerError("insufficient balance in protected account")
            self._balances = updated
            self._transactions[transaction_id] = entries
            return True

    def balance(self, account: str, asset: str) -> int:
        with self._lock:
            return self._balances.get((account, asset), 0)

    def transactions(self):
        with self._lock:
            return dict(self._transactions)
