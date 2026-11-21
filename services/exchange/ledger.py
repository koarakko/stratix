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
        self._reservations = {}
        self._held = {}
        self._fills = {}
        self._lock = RLock()

    def post(self, transaction_id: str, postings) -> bool:
        return self._post(transaction_id, postings)

    def _post(self, transaction_id: str, postings, *, _internal=False) -> bool:
        if not isinstance(transaction_id, str) or not transaction_id.strip():
            raise LedgerError("transaction id must be nonempty")
        if not _internal and transaction_id.startswith(("reservation-fill:", "reservation-settle:")):
            raise LedgerError("reserved transaction id namespace")
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
            if any(amount < self._held.get((account, asset), 0)
                   for (account, asset), amount in updated.items()
                   if account in self._protected_accounts):
                raise LedgerError("insufficient available balance in protected account")
            self._balances = updated
            self._transactions[transaction_id] = entries
            return True


    def reserve(self, reservation_id: str, account: str, asset: str, amount: int) -> bool:
        """Hold available funds without changing booked balance."""
        if not isinstance(reservation_id, str) or not reservation_id.strip():
            raise LedgerError("reservation id must be nonempty")
        if not isinstance(account, str) or not account.strip() or not isinstance(asset, str) or not asset.strip():
            raise LedgerError("account and asset must be nonempty")
        if type(amount) is not int or amount <= 0:
            raise LedgerError("reservation amount must be a positive integer")
        with self._lock:
            previous = self._reservations.get(reservation_id)
            if previous is not None:
                if previous[:3] == (account, asset, amount):
                    return False
                raise LedgerError("conflicting reservation id")
            if account not in self._protected_accounts:
                raise LedgerError("reservations require a protected account")
            key = (account, asset)
            if self._balances.get(key, 0) - self._held.get(key, 0) < amount:
                raise LedgerError("insufficient available balance")
            self._held[key] = self._held.get(key, 0) + amount
            self._reservations[reservation_id] = (account, asset, amount, 'held', None)
            return True

    def release(self, reservation_id: str) -> bool:
        with self._lock:
            reservation = self._reservations.get(reservation_id)
            if reservation is None:
                raise LedgerError("unknown reservation")
            account, asset, amount, state, destination = reservation
            if state == 'released':
                return False
            if state not in ('held', 'partial'):
                raise LedgerError("reservation already settled")
            key = (account, asset)
            self._held[key] -= amount
            self._reservations[reservation_id] = (account, asset, amount, 'released', None)
            return True

    def settle(self, reservation_id: str, destination: str) -> bool:
        if not isinstance(destination, str) or not destination.strip():
            raise LedgerError("destination must be nonempty")
        with self._lock:
            reservation = self._reservations.get(reservation_id)
            if reservation is None:
                raise LedgerError("unknown reservation")
            account, asset, amount, state, previous_destination = reservation
            if state == 'settled':
                if previous_destination == destination:
                    return False
                raise LedgerError("conflicting settlement destination")
            if state != 'held':
                raise LedgerError("reservation is not an untouched hold")
            if destination == account:
                raise LedgerError("destination must differ from source")
            key = (account, asset)
            self._held[key] -= amount
            try:
                if not self._post('reservation-settle:' + reservation_id,
                                 (Posting(account, asset, -amount), Posting(destination, asset, amount)), _internal=True):
                    raise LedgerError('settlement transaction id already used')
            except Exception:
                self._held[key] += amount
                raise
            self._reservations[reservation_id] = (account, asset, amount, 'settled', destination)
            return True

    def settle_partial(self, reservation_id: str, destination: str, amount: int, fill_id: str) -> bool:
        """Settle a uniquely identified partial fill; keep the unfilled balance held."""
        if not isinstance(fill_id, str) or not fill_id.strip():
            raise LedgerError("fill id must be nonempty")
        if not isinstance(destination, str) or not destination.strip():
            raise LedgerError("destination must be nonempty")
        if type(amount) is not int or amount <= 0:
            raise LedgerError("fill amount must be a positive integer")
        with self._lock:
            previous = self._fills.get(fill_id)
            request = (reservation_id, destination, amount)
            if previous is not None:
                if previous == request:
                    return False
                raise LedgerError("conflicting fill id")
            reservation = self._reservations.get(reservation_id)
            if reservation is None:
                raise LedgerError("unknown reservation")
            account, asset, remaining, state, _ = reservation
            if state not in ('held', 'partial'):
                raise LedgerError("reservation is closed")
            if destination == account:
                raise LedgerError("destination must differ from source")
            if amount > remaining:
                raise LedgerError("fill exceeds remaining reservation")
            key = (account, asset)
            self._held[key] -= amount
            try:
                applied = self._post('reservation-fill:' + fill_id,
                                    (Posting(account, asset, -amount),
                                     Posting(destination, asset, amount)), _internal=True)
                if not applied:
                    raise LedgerError("fill transaction id already used")
            except Exception:
                self._held[key] += amount
                raise
            left = remaining - amount
            self._reservations[reservation_id] = (account, asset, left,
                                                   'settled' if left == 0 else 'partial',
                                                   destination if left == 0 else None)
            self._fills[fill_id] = request
            return True

    def available(self, account: str, asset: str) -> int:
        with self._lock:
            key = (account, asset)
            return self._balances.get(key, 0) - self._held.get(key, 0)

    def balance(self, account: str, asset: str) -> int:
        with self._lock:
            return self._balances.get((account, asset), 0)

    def transactions(self):
        with self._lock:
            return dict(self._transactions)
