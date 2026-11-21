"""Independent, read-only audit of in-memory ledger transaction snapshots."""
from collections.abc import Mapping


class LedgerAuditError(ValueError):
    """A transaction snapshot is malformed or differs from expected balances."""


def audit_transactions(transactions, expected_balances=None):
    """Recalculate account/asset balances from balanced immutable postings.

    Zero balances are omitted from the result and comparison. This checks only
    the supplied snapshot; it cannot prove its completeness or authenticity.
    """
    if not isinstance(transactions, Mapping):
        raise LedgerAuditError("transactions must be a mapping")
    balances = {}
    for transaction_id, entries in transactions.items():
        if not isinstance(transaction_id, str) or not transaction_id.strip():
            raise LedgerAuditError("invalid transaction id")
        if not isinstance(entries, (tuple, list)) or len(entries) < 2:
            raise LedgerAuditError("transaction requires at least two postings")
        totals = {}
        for posting in entries:
            account = getattr(posting, 'account', None)
            asset = getattr(posting, 'asset', None)
            amount = getattr(posting, 'amount', None)
            if (not isinstance(account, str) or not account.strip()
                    or not isinstance(asset, str) or not asset.strip()
                    or type(amount) is not int or amount == 0):
                raise LedgerAuditError("invalid posting")
            totals[asset] = totals.get(asset, 0) + amount
            key = (account, asset)
            balances[key] = balances.get(key, 0) + amount
        if any(totals.values()):
            raise LedgerAuditError("transaction does not balance per asset")
    result = {key: amount for key, amount in balances.items() if amount != 0}
    if expected_balances is not None:
        if not isinstance(expected_balances, Mapping):
            raise LedgerAuditError("expected balances must be a mapping")
        expected = {}
        for key, amount in expected_balances.items():
            if (not isinstance(key, tuple) or len(key) != 2
                    or any(not isinstance(v, str) or not v.strip() for v in key)
                    or type(amount) is not int):
                raise LedgerAuditError("invalid expected balance")
            if amount:
                expected[key] = amount
        if result != expected:
            raise LedgerAuditError("recalculated balances differ from expected")
    return result
