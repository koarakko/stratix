# In-memory double-entry ledger (educational)

`services.exchange.ledger` is a standalone reference for balanced, atomic
**in-process** journal entries. It is not connected to the exchange matcher,
CommandJournal, or FencingGate and is **not production ready**.

Each `Posting(account, asset, amount)` has a nonzero signed integer amount in
the asset's smallest application-defined unit. A transaction contains at least
two postings and must sum to zero **separately for every asset**. Positive
amounts credit an account; negative amounts debit it. This convention is a
simplified transfer ledger, not a full accounting chart of accounts.

`Ledger.post(id, postings)` returns True on first acceptance and False on an
identical retry. A reused ID with different postings, invalid data, or an
unbalanced transaction raises `LedgerError` without modifying balances.
An `RLock` serializes updates and same-process retries. Immutable postings
and a tuple snapshot prevent caller-side list mutation from changing history.

Example:

```python
from services.exchange.ledger import Ledger, Posting
ledger = Ledger()
ledger.post("transfer-1", [Posting("alice", "BTC", -5), Posting("bob", "BTC", 5)])
assert ledger.balance("bob", "BTC") == 5
```

Run `python3 -m unittest discover -s tests -p 'test_ledger.py' -v`.

**Limits:** balances may become negative; there is no balance reservation,
authorization, fee model, persistence, recovery, consensus, cross-process
coordination, atomic storage commit, or durable idempotency. Restart discards
all state. Never use this for real customer balances or settlement.

## Optional nonnegative accounts

Construct `Ledger(protected_accounts={"alice", "bob"})` to reject any
transaction whose **final** balance for those accounts becomes negative in any
asset. The check runs under the same process-local lock as balance updates and
transaction-ID recording; a rejected transaction does not consume its ID.
Multiple postings for one account/asset are netted before the check. Other
accounts, such as an explicitly modeled issuance/clearing account, can carry
negative balances. Account protection is fixed at construction time.

```python
ledger = Ledger(protected_accounts={"alice"})
ledger.post("fund", [Posting("issuance", "BTC", -10), Posting("alice", "BTC", 10)])
ledger.post("spend", [Posting("alice", "BTC", -4), Posting("merchant", "BTC", 4)])
assert ledger.balance("alice", "BTC") == 6
```

This is **not** a reservation mechanism: there is no hold/available-balance
distinction, persistence, distributed concurrency control, or authorization.
The default constructor remains unrestricted for compatibility. A new Ledger
instance starts empty, so replay/persistence must be implemented before any
restart-safe balance enforcement is possible. Run
`python3 -m unittest discover -s tests -p 'test_ledger_protected.py' -v`.
