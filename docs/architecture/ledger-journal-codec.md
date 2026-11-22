# Ledger journal command payload (experimental)

The versioned `services.exchange.ledger_journal_codec` module defines a strict JSON-safe payload for future Ledger-to-CommandJournal integration. Supported operations: `post`, `reserve`, `release`, `settle`, and `settle_partial`. `post` carries a list of at least two per-asset-balanced integer postings, rejecting reserved transaction ID namespaces. The envelope has exactly `type: "ledger"`, `version: 1`, and a `command` object. Unknown fields, operations, versions, non-string identifiers, and non-positive or non-integer amounts fail closed.

```python
from services.exchange.ledger_journal_codec import encode_ledger_command, decode_ledger_command
payload = encode_ledger_command("reserve", reservation_id="r1", account="alice", asset="BTC", amount=5)
operation, fields = decode_ledger_command(payload)
```

Run `python3 -m unittest discover -s tests -p 'test_ledger_journal_codec.py' -v`.

**Not a persistence or recovery mechanism:** This codec does not append to `CommandJournal`, execute commands against `Ledger`, validate business state, reconstruct booked balances, or provide an atomic journal/ledger commit. It is not safe to replay untrusted commands into a live ledger without a separate validated recovery protocol. The `post` codec can represent funding, but no funding replay or durable recovery exists yet; no real money or production use. The next vertical slice must integrate actual Journal entries, funding transactions, and deterministic replay with fail-closed tests.

## Caller-owned input isolation

`encode_ledger_command('post', ...)` now copies and normalizes each posting into a new JSON-safe dictionary. Mutating the caller's original list or posting dictionaries after encoding does not change the returned command. The returned payload itself is mutable; callers must not mutate it after handing it to a journal. This is not durable recovery or an atomic ledger commit.

Regression: `python3 -m unittest discover -s tests -p 'test_ledger_codec_isolation.py' -v`.

## Read-only replay preflight

`services.exchange.ledger_replay_plan.plan_ledger_replay(journal.entries())` checks the entire sequence (starting at 1), strict entry shape, and versioned ledger command schema before returning an immutable tuple of normalized commands. Any invalid later entry rejects the whole plan; no partially built plan is returned. The input snapshot must come from `CommandJournal.entries()` to obtain its independent on-disk checksum/history verification. The plan snapshots posting values so later caller mutation cannot change them.

This is **not** Ledger recovery: it does not execute Ledger operations, validate reservation/business transitions, verify a journal's authenticity, persist balances, or fence a second leader. A later recovery implementation must replay into a private Ledger, fail closed on any business error, and publish the new instance only after complete success. Never use this as a production trading recovery path.

Regression: `python3 -m unittest discover -s tests -p 'test_ledger_replay_plan.py' -v`.
