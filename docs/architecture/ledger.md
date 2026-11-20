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
