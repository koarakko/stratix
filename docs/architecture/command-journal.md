# Local checksummed command journal (educational)

`services/exchange/command_log.py` provides an **opt-in**, single-writer
append-only JSON-lines journal. It is not connected to `SequencedExchange`
and must not be described as durable order acceptance or consensus.

Each line contains a strictly increasing, 1-based sequence, a JSON payload,
and SHA-256 of its canonical data representation. `append(sequence, payload)`
uses append mode and `fsync` before returning `True`. An identical committed
retry returns `False`; conflicting sequences, gaps, non-JSON values and NaN
are rejected. Reopening checks checksums, canonical encoding, and sequence
continuity. A truncated final line, reordered line, or modified payload
raises `JournalError` and **does not automatically truncate or repair** the
file. An I/O write failure poisons the current instance; it cannot retry.

Example from the repository root:

```python
from services.exchange.command_log import CommandJournal
journal = CommandJournal("/tmp/stratix-example.journal")
journal.append(1, {"type": "place", "order_id": "demo-1", "quantity": "1.25"})
assert CommandJournal("/tmp/stratix-example.journal").entries()[0]["sequence"] == 1
```

Run `python3 -m unittest discover -s tests -p 'test_command_log.py' -v`.

## Safety limitations

- **Not production safe**: no Raft/quorum, lease/epoch fencing, cross-region
  replication, transactional matching, or guaranteed durable acknowledgement.
- No concurrent writers or external file modification: multiple processes can
  race despite `O_APPEND`. No advisory lock, inode checking, or process fencing.
- Creating a new file does not sync its parent directory. Power-loss durability
  and hardware flush guarantees are platform/filesystem-dependent.
- A short write can leave a corrupt tail. Recovery requires an explicit
  operator decision; never silently discard a possibly committed command.
- SHA-256 detects accidental corruption, **not malicious tampering** by a party
  who can rewrite the data and its checksum.
- The journal only validates generic JSON dictionaries. It does not validate
  order economics, reserve funds, or replay commands into the exchange.

Next: define a canonical codec for `PlaceOrder`/`CancelOrder`, then add
an explicitly recoverable sequenced exchange with fail-closed tests.
