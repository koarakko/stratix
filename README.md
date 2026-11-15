# stratix

Infrastructure for resilient digital asset exchanges.

> **Educational reference implementation — not production ready.** The trading
> components currently use in-memory state without persistence, consensus,
> balance reservation, ledger settlement, or leader fencing. Do not trade real
> assets or deploy them as a production exchange.

## Local verification

Use Python 3.10+ from the repository root; no AWS account is required:

```sh
python3 -m unittest discover -s tests -v
```

The sequenced order/matching reference includes an independently verified
[lifecycle projection](docs/architecture/sequenced-exchange.md) that covers
open, partially filled, filled, and cancelled orders. It rejects disagreements
between the matching engine's remaining amounts and the projected state.

A separate [local checksummed command journal](docs/architecture/command-journal.md)
illustrates append, fsync, retry, and fail-closed corruption detection. Its\n`entries()` accessor revalidates the on-disk journal before returning records. It is
not yet connected to the matching engine and is not a replicated commit log.
A [versioned order-command codec](services/exchange/journal_codec.py) can
replay the checked journal into a new in-memory order state machine or, using
`recover_exchange()`, reconstruct deterministic fills, remaining quantities,
and order lifecycles in a new `SequencedExchange`. Recovery is read-only and
fail-closed; it does not provide atomic matching, consensus, fencing, or
production durability.
Injected [journal I/O failure tests](tests/test_journal_io_failure.py) cover short writes, fsync failures and ambiguous recovery; they do not simulate actual power loss.

The longer-term goal is a Terraform-based, multi-region AWS architecture with
replayable matching, double-entry ledger, recovery testing, and documented
consistency trade-offs. **None of these aspirations is a production guarantee.**
Observed empty-journal deletion is also rejected; see [empty journal deletion tests](tests/test_journal_empty_file_deletion.py). This is not inode fencing or concurrent-writer safety.
