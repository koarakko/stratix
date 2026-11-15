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


## Versioned order command codec and read-only recovery

`services/exchange/journal_codec.py` defines version-1 payloads for
`PlaceOrder` and `CancelOrder`. Prices and quantities are canonical positive,
finite decimal **strings** (not JSON floats); unknown versions, extra fields,
invalid sides, and malformed values fail closed. The journal's envelope stores
the 1-based sequence separately. Encoding is explicit, and decoding checks
the entire schema before creating a command.

Example (educational only):

```python
from decimal import Decimal
from services.exchange.command_log import CommandJournal
from services.exchange.journal_codec import encode_command, recover_order_state
from services.orders.model import Command, PlaceOrder

journal = CommandJournal("/tmp/stratix-orders.journal")
command = Command(1, PlaceOrder("demo-1", "acct", "BTC-USD", "buy",
                                Decimal("100"), Decimal("1")))
journal.append(command.sequence, encode_command(command))
state = recover_order_state(CommandJournal("/tmp/stratix-orders.journal"))
assert state.history() == (command,)
```

`recover_order_state()` re-reads and validates the complete journal, then
replays all commands into a **new OrderStateMachine**. Invalid order history,
unknown schema, checksums, or torn records reject recovery; no partial state is
returned and no file is repaired. It does **not** recover a MatchingEngine or
the `SequencedExchange`, and does not make journal append and matching atomic.
A journal record might be persisted without corresponding matching execution;
do not treat append as accepted trade execution. The order state machine also
does not track fills.

Run `python3 -m unittest discover -s tests -p 'test_journal_codec.py' -v`.

Next: read-only replay into `SequencedExchange`, followed by explicit
transactional acknowledgement/recovery semantics and fencing design.

## External file mutation detection

An already-open `CommandJournal` now re-reads disk before each append (including
idempotent retries), and checks that its observed records have not changed.
If a previously nonempty journal disappears, becomes empty, or acquires
externally appended records, it raises `JournalError` rather than accepting
an acknowledgement or silently recreating a missing history. A newly created
empty journal path remains supported.

This is **detection, not locking or fencing**: another writer may change the
file between verification and `os.open`/`os.write` (TOCTOU). No cross-process
safety or transactional durability is claimed. Run
`python3 -m unittest discover -s tests -p 'test_journal_external_mutation.py' -v`.
