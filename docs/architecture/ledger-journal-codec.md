# Ledger journal command payload (experimental)

The versioned `services.exchange.ledger_journal_codec` module defines a strict JSON-safe payload for future Ledger-to-CommandJournal integration. Supported operations: `reserve`, `release`, `settle`, and `settle_partial`. The envelope has exactly `type: "ledger"`, `version: 1`, and a `command` object. Unknown fields, operations, versions, non-string identifiers, and non-positive or non-integer amounts fail closed.

```python
from services.exchange.ledger_journal_codec import encode_ledger_command, decode_ledger_command
payload = encode_ledger_command("reserve", reservation_id="r1", account="alice", asset="BTC", amount=5)
operation, fields = decode_ledger_command(payload)
```

Run `python3 -m unittest discover -s tests -p 'test_ledger_journal_codec.py' -v`.

**Not a persistence or recovery mechanism:** This codec does not append to `CommandJournal`, execute commands against `Ledger`, validate business state, reconstruct booked balances, or provide an atomic journal/ledger commit. It is not safe to replay untrusted commands into a live ledger without a separate validated recovery protocol. In particular, there is no `post` operation or funding replay yet; no real money or production use. The next vertical slice must integrate actual Journal entries, funding transactions, and deterministic replay with fail-closed tests.
