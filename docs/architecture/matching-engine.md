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

This component is **not production-safe**: no sequence-enforced
input, persistent log, Raft, leader fencing, risk checks, reserved balances,
fees, self-trade prevention, trading halts, market precision limits, or ledger
settlement. A caller must not treat `submit` as durable acceptance. The
independent `OrderStateMachine` is **not yet wired** to this matcher; in a
production design only committed sequenced commands should drive execution.
Execution IDs are local and must not be used as globally durable identifiers.

## Cancelling resting liquidity

`cancel(order_id)` removes the unfilled remainder of an existing open order
from the book and returns the removed quantity. It rejects unknown, fully
filled, and already cancelled orders; rejection does not mutate book state.
A cancelled order ID cannot be reused. Historical fills are immutable and
a partially filled order can only cancel its outstanding remainder.

`replay_actions([LimitOrder(...), CancelRequest(order_id), ...])` deterministically
rebuilds fills and remaining quantities when provided the exact same ordered
action stream. The original `replay(orders)` remains for place-only streams.
Neither method provides durable storage or replicated consensus. Cancellation
is **not** yet connected to the independent order state machine; that model
still treats partially filled orders as open without tracking filled quantity.

Run the targeted checks with
`python3 -m unittest discover -s tests -p 'test_matching*.py' -v`.

Next: connect committed, sequenced order commands to matching and test
replay across placements and cancellations, before adding ledger settlement.
