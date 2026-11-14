# Deterministic limit-order matching (educational prototype)

`services/matching/model.py` implements a single-writer, in-memory price-time
priority matching model. Only positive, finite `Decimal` limit prices and
quantities are accepted. An incoming order crosses resting opposite-side
orders in the **same market** when its limit permits. Best price wins, then
insertion order (FIFO). Each execution uses the **resting maker's price**;
partial fills leave the unfilled quantity resting. Execution IDs increment
monotonically within the engine. Replaying the same ordered input reproduces
execution events, but the engine does not persist that input.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

This component is **not production-safe**: no cancellation, sequence-enforced
input, persistent log, Raft, leader fencing, risk checks, reserved balances,
fees, self-trade prevention, trading halts, market precision limits, or ledger
settlement. A caller must not treat `submit` as durable acceptance. The
independent `OrderStateMachine` is **not yet wired** to this matcher; in a
production design only committed sequenced commands should drive execution.
Execution IDs are local and must not be used as globally durable identifiers.

Next: integrate sequenced order commands with matching and verify deterministic
replay of fills before connecting double-entry ledger postings.
