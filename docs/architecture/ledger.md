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

**Limits:** unrestricted balances may become negative; reservations are local-only,
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

Protected accounts additionally support in-memory holds described below. There is no persistence, distributed concurrency control, or authorization.
The default constructor remains unrestricted for compatibility. A new Ledger
instance starts empty, so replay/persistence must be implemented before any
restart-safe balance enforcement is possible. Run
`python3 -m unittest discover -s tests -p 'test_ledger_protected.py' -v`.

## Local balance reservations (educational)

For a protected account, `reserve(reservation_id, account, asset, amount)` holds
a positive integer quantity without changing the booked balance. `available`
returns booked balance minus active holds. A direct `post` cannot spend held
funds. `release(id)` cancels a hold; `settle(id, destination)` transfers its
entire quantity using balanced postings and consumes the hold. Both operations
are serialized under the Ledger's in-process lock. Exact retries return False;
conflicting reservation IDs, destination changes, invalid transitions, and
insufficient funds raise `LedgerError`.

```python
ledger = Ledger(protected_accounts={"alice"})
ledger.post("fund", [Posting("issuer", "BTC", -10), Posting("alice", "BTC", 10)])
ledger.reserve("order-1", "alice", "BTC", 6)
assert ledger.available("alice", "BTC") == 4
ledger.settle("order-1", "merchant")
assert ledger.balance("merchant", "BTC") == 6
```

Settlement uses the transaction ID `reservation-settle:<id>`. Public
`post()` rejects both `reservation-settle:` and `reservation-fill:` prefixes,
including exact retries, before modifying state. Only internal settlement
paths may write these IDs. A rejected direct post leaves balances, holds and
transaction history unchanged. Reservation state and holds are **in memory only**, not
recorded in CommandJournal or the transaction history. Restart loses all holds,
and there is no partial fill, expiry, distributed fencing, recovery, or
durable atomicity. The reservation methods require protected source accounts.
Do not use this for real customer assets. Run
`python3 -m unittest discover -s tests -p 'test_ledger_reservations.py' -v`.

## Partial fills (in-process only)

`settle_partial(reservation_id, destination, amount, fill_id)` debits only the
specified positive integer amount and retains the remaining reservation hold.
Each fill ID is unique across the Ledger: an identical retry returns False,
while a conflicting retry fails without changing balances. Overfills and
settlement after release are rejected. `release(id)` after partial fills
releases only the unfilled remainder. The original `settle(id, destination)`
only works on untouched holds; after a partial fill it rejects the request.

```python
ledger.reserve("order-2", "alice", "BTC", 5)
ledger.settle_partial("order-2", "merchant", 2, "trade-1")
ledger.release("order-2")  # releases remaining 3
```

Fill transactions use `reservation-fill:<fill_id>`. Public `post()` rejects
this reserved namespace, preventing external callers from preempting fill IDs.
This is a process-local API boundary, not authorization against code with
access to private methods or the Ledger's mutable internals.
Neither fill IDs nor reservation state survive restart; no storage-level
atomicity, distributed fencing, or cross-process exactly-once semantics exist.
Run `python3 -m unittest discover -s tests -p 'test_ledger_partial.py' -v`.

Run `python3 -m unittest discover -s tests -p 'test_ledger_namespace.py' -v` for namespace, retry and concurrency regressions. This does not provide durable exactly-once settlement.

## Settlement completion mode

A reservation exhausted through `settle_partial()` is closed, but is **not** an
idempotent retry of `settle()`. Calling `settle()` after full consumption by
fills raises `LedgerError` even when the destination matches. Only a prior
successful full `settle()` permits an identical full-settlement retry to return
False. Existing fill IDs remain idempotent after closure. The decision is based
on the internally recorded `reservation-settle:<id>` transaction and remains
process-local; neither this history nor holds survive restart.
Run `python3 -m unittest discover -s tests -p 'test_ledger_settlement_modes.py' -v`.

## Independent transaction snapshot audit

`audit_transactions(ledger.transactions(), expected_balances=None)` in
`services.exchange.ledger_audit` independently recalculates account/asset
balances from the supplied transaction snapshot. It rejects malformed IDs,
postings, unbalanced per-asset transactions, and mismatched expected balances
with `LedgerAuditError`. Returned balances omit zero-valued entries; expected
balances use the same normalization. The function does not modify its input.

```python
from services.exchange.ledger_audit import audit_transactions
balances = audit_transactions(ledger.transactions())
assert balances[("alice", "BTC")] == ledger.balance("alice", "BTC")
```

This audit is read-only and **cannot prove that a snapshot is complete or
untampered**, or reconstruct reservations/holds, which are not in the
transaction history. A consistent snapshot must be supplied by the caller;
concurrent changes after snapshot collection are outside its scope. It is not
a durable replay or reconciliation mechanism. Run
`python3 -m unittest discover -s tests -p 'test_ledger_audit.py' -v`.

Multi-asset reconciliation regression tests cover balanced BTC/ETH transfers,
per-asset imbalance, expected-balance asset mismatches, and input immutability.
Run `python3 -m unittest discover -s tests -p 'test_ledger_audit_multiasset.py' -v`.

## Ledger-to-audit integration regression

The integration suite uses the actual `Ledger`, `Posting`, and
`audit_transactions` implementations, not mocks. It verifies reconciliation
after reserve, partial fill, release, full settlement, idempotent retry,
rejected overfill, and concurrent fill-ID retries. It also tests malformed
postings and missing transactions against independently supplied expected
balances. Run:

```sh
python3 -m unittest discover -s tests -p 'test_ledger_audit_integration.py' -v
```

**Important:** Holds and release events do not appear in `transactions()`.
Reconciliation of booked balances therefore cannot detect an incorrect hold
or prove that a snapshot is complete. The expected balances in these tests
are read separately from the same in-memory Ledger, not an independent durable
source of truth. This is a regression test, not production reconciliation,
crash recovery, or split-brain protection.

## Reservation ID retries after state transitions

Only an identical `reserve()` retry while the reservation is an untouched
`held` reservation returns False. Once a reservation is partially filled,
fully filled, settled, or released, reusing its ID raises `LedgerError`
even if the original account, asset, and amount match. This prevents callers
from treating a closed or changed reservation as an active hold. Rejection
leaves booked balances, held amounts, and transaction history unchanged.
Reservation IDs remain process-local and are lost on restart.
Run `python3 -m unittest discover -s tests -p 'test_ledger_reservation_retry_states.py' -v`.
