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

The longer-term goal is a Terraform-based, multi-region AWS architecture with
replayable matching, double-entry ledger, recovery testing, and documented
consistency trade-offs. **None of these aspirations is a production guarantee.**
