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
`SequencedExchange` adapter now connects committed in-memory order commands
to matching and checks replay and independent event invariants. This is not a
durable consensus commit and provides no fencing or concurrent-writer safety.
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
is connected through `SequencedExchange`; the underlying order state machine
still treats partially filled orders as open, while the integrated lifecycle
projection reports fills and cancelled remainder.

Run the targeted checks with
`python3 -m unittest discover -s tests -p 'test_matching*.py' -v`.

## Price/time priority regression

`tests/test_matching_priority_regression.py` asserts explicit maker order and
fill quantities independently of the matcher replay oracle. It checks best ask
for buy takers, best bid for sell takers, FIFO within a price level, priority
retention after partial fills, cancellation removing the earliest maker, and
market isolation/non-crossing orders. A deterministic replay matching itself
is insufficient evidence of correct price/time priority, so these assertions
use fixed expected executions.

Run: `python3 -m unittest discover -s tests -p 'test_matching_priority_regression.py' -v`.

Next: add a separate reference order-book oracle or property-based tests for
larger streams, then move toward durable sequenced commands and ledger posting.
