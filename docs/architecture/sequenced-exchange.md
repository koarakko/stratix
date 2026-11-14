# Sequenced matching integration (educational)

`services/exchange/sequenced.py` bridges the order command state machine and
price-time matching engine. Each accepted 1-based command is applied to
**copies** of both in-memory models, then both copies are published together.
An identical committed retry returns no new executions; a conflicting or
skipped sequence fails without changing either model. Even an identical retry
revalidates the committed execution events and remaining quantities before
returning an empty fill list; corrupted state raises `LifecycleConsistencyError`
instead of silently acknowledging the command. Cancellation of a fully
filled order is rejected and does not consume the command sequence. Replaying
accepted commands reconstructs the same execution events and open quantities.

## Unified order lifecycle and consistency checks

`SequencedExchange.lifecycle()` derives a fresh `dict[str, OrderLifecycle]` from
its committed commands and matching execution events. The four statuses are
`open`, `partially_filled`, `filled`, and `cancelled`. It preserves filled
quantities after cancellation and reports the unfilled cancelled quantity
separately. The projection is checked against the matching engine's independently
tracked remaining quantity **for every order**, raising
`LifecycleConsistencyError` on disagreement. `apply()` performs the same check
on copied candidate state **before** publishing a new accepted command; a
failure does not consume a sequence number or publish new execution events.

In addition to checking aggregate remaining quantities, every accepted command
is converted into a matching action and replayed through a fresh MatchingEngine.
The resulting **ordered execution events** (including IDs, maker/taker IDs,
market, price and quantity) must match the live engine's events exactly. This
detects corrupted event identities and prices that aggregate quantity checks
alone would miss. Reconstructed remaining quantities must also agree with both
the lifecycle projection and live book. A disagreement raises
`LifecycleConsistencyError`; a new command is not published. This replay
validation is O(history + replay matching cost) for every accepted command
and snapshot, deliberately trading performance for a simple consistency
oracle. It is **not independent verification** against a compromised command
log or matching algorithm; a trustworthy durable log and replicated consensus
remain necessary.

The dictionary returned to callers is a fresh object containing frozen lifecycle
records. This does **not** provide a concurrent read transaction. Only a single
external writer/reader at a time is supported.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_sequenced*.py' -v
python3 -m unittest discover -s tests -p 'test_execution_causality.py' -v
python3 -m unittest discover -s tests -p 'test_retry_integrity.py' -v
python3 -m unittest discover -s tests -v
```

The integration checks cover deterministic replay, partial/full fills, cancel
quantities, identical retries, failed cancellation rollback, snapshot isolation,
and deliberately corrupted matching remaining quantities, event prices,
execution IDs and maker identities. Retry integrity checks cover valid
idempotent place/cancel commands and rejection of retries after deliberate
execution-price or remaining-quantity corruption.

## Explicit safety limits

- **Not production ready.** This is a single-process in-memory reference, not
  a durable command log, transactional database, or Raft implementation.
- Deep-copy-and-swap is not thread-safe; external single-writer serialization
  is required. No leader fencing, term/epoch validation, quorum, or crash
  recovery exists.
- The order state machine itself still labels a fully executed order `open`;
  use `SequencedExchange.lifecycle()` for the unified projection. The standalone
  `project_lifecycle()` assumes consistent input and does not verify event
  ordering, prices, markets, sides or execution identity uniqueness. The
  integrated accessor now replays committed commands to check these event
  fields, but cannot independently prove the matching algorithm is correct.
- No funds reservation, settlement, ledger posting, fees, market tick/lot
  constraints, or self-trade prevention. Never accept real customer orders.
- Deep-copy cost grows with history and book size; this deliberately favors
  simple atomic error handling over performance.

Next: add independent event invariants and a bounded replay checkpoint before
integrating ledger settlement.
