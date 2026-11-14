# Sequenced matching integration (educational)

`services/exchange/sequenced.py` bridges the existing order command state machine
and price-time matching engine. Each accepted 1-based command is applied to
**copies** of both in-memory models, then both copies are published together.
An identical committed retry returns no new executions; a conflicting or
skipped sequence fails without changing either model. Cancellation of a fully
filled order is rejected and does not consume the command sequence. Replaying
accepted commands reconstructs the same execution events and open quantities.

From the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The integration tests cover deterministic execution replay, cancellation and
retry, rollback after invalid cancellation, and sequence conflicts/gaps.

## Explicit safety limits

- **Not production ready.** This is a single-process in-memory reference, not
  a durable command log, transactional database, or Raft implementation.
- Deep-copy-and-swap is not thread-safe; external single-writer serialization
  is required. No leader fencing, term/epoch validation, quorum, or crash
  recovery exists.
- The order state machine still labels a fully executed order as `open`;
  the matching engine owns remaining quantity. The adapter rejects cancellation
  of filled orders but does not expose a unified lifecycle projection.
- No funds reservation, settlement, ledger posting, fees, market tick/lot
  constraints, or self-trade prevention. Never accept real customer orders.
- Deep-copy cost grows with history and book size; this deliberately favors
  simple atomic error handling over performance.

Next: add an explicit unified order lifecycle projection (open/partial/filled/
cancelled) and test replay invariants before integrating ledger settlement.
