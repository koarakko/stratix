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
illustrates append, fsync, retry, and fail-closed corruption detection. It is
not yet connected to the matching engine and is not a replicated commit log.
A [versioned order-command codec](services/exchange/journal_codec.py) can
replay the checked journal into a new in-memory order state machine; it does
not provide atomic matching, consensus, or production durability.

The longer-term goal is a Terraform-based, multi-region AWS architecture with
replayable matching, double-entry ledger, recovery testing, and documented
consistency trade-offs. **None of these aspirations is a production guarantee.**
