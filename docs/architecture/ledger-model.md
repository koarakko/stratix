# In-memory ledger reference model

Status: **educational executable model**, not production ready.

The Python standard-library model in `services/ledger/model.py` represents a journal posting as an immutable transaction ID plus a tuple of signed account/asset entries. A valid posting has at least two nonzero finite `Decimal` entries and sums to zero **for each asset independently**. A repeated transaction ID with identical entries is a no-op; reusing an ID with different entries is an error. Invalid postings do not mutate the journal or balances. Replaying a journal reconstructs balances deterministically. **Recovery replay is strict:** a repeated transaction ID in the supplied journal (even an identical duplicate) raises `DuplicateJournalEntryError`. This differs intentionally from online `post()`, where an identical retry is a no-op. A duplicate in a supposedly canonical recovery stream indicates an upstream export, log, or recovery defect and must not be silently hidden.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

## Explicit limitations

- In-memory only: a process crash loses all entries; no disk, quorum, replication, or durability guarantee.
- Not thread-safe and no atomic storage transaction. Concurrent writers are unsupported.
- Negative balances are permitted: this model proves journal conservation, **not** pre-trade balance authorization or collateral safety.
- No amount scale or precision policy, custody controls, transaction signatures, audit retention, or settlement finality.
- Journal entries preserve insertion order only within a single process. Cross-region ordering, fencing epochs and recovery are future work.

Next: add a deterministic order-command state machine with duplicate order IDs and explicit sequence numbers; later introduce durable storage and single-writer fencing before any AWS deployment claim.
