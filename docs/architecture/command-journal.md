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
- Cooperating same-host POSIX writers use a persistent advisory `flock` sidecar
  and journal/lock inode checks. Non-cooperating writers, lock-file replacement
  after verification, and external mutation can still race; there is no
  process fencing, distributed consensus, or cross-region exclusion.
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


## Read-only exchange reconstruction

`recover_exchange(journal)` in `services/exchange/journal_codec.py` reads and
validates the complete on-disk journal, decodes the versioned commands, replays
them through a new `SequencedExchange`, and verifies its lifecycle projection.
It reconstructs deterministic execution events, order statuses, fills, cancelled
quantities and open remaining quantities. Empty journals recover to empty state.

```python
from services.exchange.command_log import CommandJournal
from services.exchange.journal_codec import recover_exchange

exchange = recover_exchange(CommandJournal("/tmp/stratix-orders.journal"))
print(exchange.executions(), exchange.lifecycle())
```

Invalid schema, duplicate order identities, cancellation of filled orders,
inconsistent replay, and corrupt/truncated records abort recovery without
returning partial state or modifying the journal. Repeating recovery does not
acknowledge new orders. The returned in-memory exchange is independent of the
journal; mutating it does **not** persist commands.

**Safety boundary:** deterministic replay is not crash-safe atomic commitment.
An fsynced journal command may never have been acknowledged, and a previously
acknowledged in-memory trade may be absent from the journal. There is no quorum,
leader fencing, balance reservation, or cross-region consensus. Operators must
not infer authoritative order acceptance from replay alone.

Run `python3 -m unittest discover -s tests -p 'test_exchange_recovery.py' -v`.

## Verified snapshot reads

`CommandJournal.entries()` now re-reads and validates the journal on disk
rather than returning the cached startup snapshot. External append, deletion,
truncated records and checksum corruption fail closed with `JournalError`.
This avoids exposing stale cached entries as if they were current disk state.
It does **not** provide an atomic snapshot across other processes, a file lock,
or leader fencing: a writer may still race after the verification read.

Run `python3 -m unittest discover -s tests -p 'test_journal_snapshot_integrity.py' -v`.

## Injected I/O failure tests

Run `python3 -m unittest discover -s tests -p 'test_journal_io_failure.py' -v`.
The tests inject short writes, pre-write failures, and `fsync` failures using
Python mocks. A short write leaves an incomplete tail and recovery refuses it;
the original instance remains poisoned after any write/fsync failure.
If `fsync` fails **after** a full write, a later process may observe the
complete record, but this does **not** prove durability or that the client
received an acknowledgement. Such an outcome is ambiguous and requires
application-level reconciliation, not automatic resubmission as a new order.
A clean pre-write failure permits a fresh instance to retry sequence 1.

These are deterministic fault-injection tests, **not** power-loss, filesystem
crash-consistency, or distributed failover tests. There is still no replicated
commit index, leader fencing, or atomic journal/matching transaction.

## Observed empty journal deletion

An empty file that has already been observed is now treated as existing
history: if it disappears, subsequent `entries()` or `append()` calls
raise `JournalError` instead of silently recreating it. A path that was
missing from initialization may still be created by the first append. This
closes a deletion-detection gap for empty journals but does **not** prevent
replacement of a file with another valid empty file, inode substitution, or
concurrent writer races. Run
`python3 -m unittest discover -s tests -p 'test_journal_empty_file_deletion.py' -v`.

## Journal file identity checks

The journal remembers the device/inode of the file it first reads or creates. Each read checks the opened descriptor and path identity; each append checks the opened descriptor before writing. Replacing the path with an otherwise byte-identical file raises `JournalError` for the existing instance. An operator may explicitly reopen a verified replacement file; this is not automatic repair. The checks do not close all TOCTOU races and are **not** locking, cross-process writer exclusion, leader fencing, or a durability guarantee.

Run `python3 -m unittest discover -s tests -p 'test_journal_inode_identity.py' -v`.

## Same-inode append race detection

Before writing, `append()` compares the opened descriptor and pathname sizes with the byte length verified by `read_all()`. If another writer appends after validation but before `os.open`, the changed size raises `JournalError` and poisons the instance without issuing a local write. The check also applies when the journal is initially absent (expected length zero). A clean append advances the expected length and retains idempotent retries.

This is only a **best-effort fail-closed detection**. A writer can still race after the size checks and before `os.write`, or rewrite equal-length content. It is not mutual exclusion, atomic compare-and-append, leader fencing, or a replacement for a single-writer/quorum design. See `python3 -m unittest discover -s tests -p 'test_journal_append_race.py' -v`.

## Cooperative same-host writer lock

`append()` now holds a POSIX `flock(LOCK_EX)` on a stable `<journal>.lock`
sidecar file across disk revalidation, sequence/retry checks, append and
`fsync`. A second cooperating writer blocks, then revalidates and rejects
stale/conflicting history instead of issuing a duplicate sequence.
The lock file must not be deleted or replaced while any writer runs.

This is **not** a distributed lock, security boundary, or fencing token:
non-cooperating writers can ignore `flock`; replacing the sidecar lock file
can split lock domains; network filesystems may not preserve the required
semantics. It does not solve read-only snapshot races, power-loss durability,
Raft quorum, or cross-region split brain. Linux/POSIX only; Windows unsupported.
The lock regression tests also assert that exceptions raised inside the writer
thread reach the test via `Future.result()` and verify the holder process exits
successfully. The holder is started with Python's `spawn` context rather than
forking the multithreaded test runner; this avoids inherited thread/lock state
and Python 3.12+ fork-in-multithreaded-process warnings. The test remains
POSIX-only and does not validate distributed fencing. Run `python3 -m unittest discover -s tests -p 'test_journal_lock.py' -v`.

## Sidecar replacement detection

After acquiring the advisory lock, the writer compares the device/inode of the
locked descriptor with the sidecar pathname. If the sidecar was deleted or
replaced during acquisition, append fails closed with `JournalError` before
writing a command. This is a best-effort check, **not** atomic fencing: a
replacement after the identity check can still split the lock domain. Never
remove or rotate the sidecar while writers are active. Run
`python3 -m unittest discover -s tests -p 'test_journal_lock_identity.py' -v`.
