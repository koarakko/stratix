# Deterministic order command state machine

Status: **educational executable model**, not a production matching engine.

`services/orders/model.py` provides a single-writer, in-memory command sequencer.
`PlaceOrder` records an immutable order identity, account, market, side, limit
price and quantity. `CancelOrder` changes an existing open order to cancelled.
Commands carry contiguous, 1-based sequence numbers; a retry of an identical
committed command is a no-op. A conflicting sequence, skipped sequence, reused
order ID, invalid price/quantity or invalid cancellation is rejected without
consuming a sequence number. Replaying accepted history reconstructs state.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

## Safety boundaries

- **No matching, fills, fee calculation, reservation, ledger posting, or settlement.**
- No durable log, leader epoch, writer fencing, cross-region quorum or concurrency safety.
- Order ID uniqueness is global to one state machine instance; production needs
  an explicit namespace and persistent deduplication window/policy.
- In-memory acknowledgement is **not** durable order acceptance; do not return
  success to real clients based on this model.
- Exact `Decimal` input is required, but market tick/lot-size and precision
  constraints are not yet enforced.
- Replay is deterministic for a fixed Python command stream; a production wire
  format must define canonical serialization and versioning.

Next: deterministic price-time matching and execution events, then explicit
ledger integration and invariant tests. Only after local tests should a durable
replicated command log and single-writer fencing be designed and implemented.
