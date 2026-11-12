"""Educational double-entry ledger with idempotent journal postings.

This in-memory implementation is NOT durable, concurrent, or suitable for funds.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class Entry:
    account: str
    asset: str
    amount: Decimal  # Positive = credit to account, negative = debit.


@dataclass(frozen=True)
class Posting:
    transaction_id: str
    entries: tuple[Entry, ...]


class DuplicateTransactionError(ValueError):
    """An idempotency key was reused with different journal contents."""


class Ledger:
    def __init__(self) -> None:
        self._journal: dict[str, Posting] = {}
        self._balances: dict[tuple[str, str], Decimal] = {}

    def post(self, transaction_id: str, entries: Iterable[Entry]) -> bool:
        """Apply an atomic in-memory posting; False means an identical retry."""
        items = tuple(entries)
        if not transaction_id or not transaction_id.strip():
            raise ValueError("transaction_id must be nonempty")
        if len(items) < 2:
            raise ValueError("posting requires at least two entries")
        totals: dict[str, Decimal] = {}
        for entry in items:
            if not entry.account or not entry.asset:
                raise ValueError("account and asset must be nonempty")
            if not isinstance(entry.amount, Decimal) or not entry.amount.is_finite():
                raise ValueError("amount must be a finite Decimal")
            if entry.amount == 0:
                raise ValueError("zero-value entries are not allowed")
            totals[entry.asset] = totals.get(entry.asset, Decimal(0)) + entry.amount
        if any(total != 0 for total in totals.values()):
            raise ValueError("posting must balance independently for each asset")

        posting = Posting(transaction_id, items)
        existing = self._journal.get(transaction_id)
        if existing is not None:
            if existing != posting:
                raise DuplicateTransactionError("transaction_id already used for another posting")
            return False

        # Validate before mutation; no partial application on validation errors.
        for entry in items:
            key = (entry.account, entry.asset)
            self._balances[key] = self._balances.get(key, Decimal(0)) + entry.amount
        self._journal[transaction_id] = posting
        return True

    def balance(self, account: str, asset: str) -> Decimal:
        return self._balances.get((account, asset), Decimal(0))

    def journal(self) -> tuple[Posting, ...]:
        return tuple(self._journal.values())

    @classmethod
    def replay(cls, postings: Iterable[Posting]) -> "Ledger":
        ledger = cls()
        for posting in postings:
            ledger.post(posting.transaction_id, posting.entries)
        return ledger
