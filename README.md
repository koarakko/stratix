# stratix

Infrastructure for resilient digital asset exchanges.

> **Educational reference implementation — not production ready.** The trading
> components currently use in-memory state without persistence, consensus,
> durable balance reservation, durable ledger settlement, or leader fencing. Do not trade real
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
illustrates append, fsync, retry, and fail-closed corruption detection. Its
`entries()` accessor revalidates the on-disk journal before returning records. It is
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

File identity substitution is detected for an open journal (device/inode checks); see [identity tests](tests/test_journal_inode_identity.py). This is not a multi-writer lock or fencing mechanism.

A [same-inode append race regression](tests/test_journal_append_race.py) rejects external growth detected between validation and write. Size checks narrow one race window but are not locking, fencing, or a TOCTOU guarantee.

Cooperating POSIX writers now serialize journal appends using a persistent
`<journal>.lock` sidecar; see [lock behavior and limitations](docs/architecture/command-journal.md)
and [lock tests](tests/test_journal_lock.py). This is not distributed fencing.

Sidecar replacement/deletion during lock acquisition is detected before append;
see [lock identity tests](tests/test_journal_lock_identity.py). The check is
not atomic fencing and does not make lock-file replacement safe.

A [POSIX lock-holder termination regression](tests/test_journal_lock_crash.py) verifies that an OS-terminated process releases its advisory lock, leaving previously committed bytes unchanged and allowing a fresh instance to retry or append. It does not simulate a crash during a journal write, guarantee power-loss durability, or provide distributed fencing. Run `python3 -m unittest discover -s tests -p 'test_journal_lock_crash.py' -v`.

Read-time pathname disappearance is fail-closed after a successful open, even
when the path was absent at initialization. Only an ENOENT from the initial
open of an unobserved journal is treated as an empty journal. See
[read-disappearance regression tests](tests/test_journal_read_disappearance.py).
This narrows a read race; it does not prevent concurrent mutation or provide
fencing. Run `python3 -m unittest discover -s tests -p 'test_journal_read_disappearance.py' -v`.

Advisory lock fault-injection tests also verify that a failed sidecar `fstat`
closes its file descriptor and poisons the journal instance, preventing an
unsafe retry. Run `python3 -m unittest discover -s tests -p 'test_journal_lock_failures.py' -v`.
This is local descriptor cleanup verification, not distributed fencing or
power-loss durability.

Journal verified-state regression: `python3 -m unittest discover -s tests -p 'test_journal_verified_state.py' -v` ensures failed checksum/history verification does not advance trusted file metadata. This remains a local fail-closed check, not leader fencing.

Journal payload isolation regression: `python3 -m unittest discover -s tests -p 'test_journal_payload_aliasing.py' -v` verifies that caller-owned nested payload mutations cannot alter committed in-memory history or break idempotent retries. This is not a concurrent-mutation or distributed fencing guarantee.

An [in-memory leadership-epoch fencing gate](docs/architecture/fencing-gate.md) demonstrates rejection of stale and conflicting leaders, including restart high-water-mark checks. It is not integrated with storage and provides **no distributed fencing guarantee**. Run `python3 -m unittest discover -s tests -p 'test_fencing.py' -v`.

Local gate operation serialization is demonstrated by
[`run_authorized`](docs/architecture/fencing-gate.md) and
[`test_fencing_operation.py`](tests/test_fencing_operation.py). It only
serializes leadership changes within one gate instance; it is not distributed
fencing or durable journal integration.

Same-thread callback reentrancy checks prevent an authorized operation from
replacing/revoking its own gate leader mid-callback. See
[reentrancy tests](tests/test_fencing_reentrancy.py). This is still local-only.

Local concurrent leadership-change regressions cover install/revoke waiting for
an authorized callback, stale callback rejection, and exception cleanup. See
[threaded gate tests](tests/test_fencing_threading.py). They do not establish
distributed linearizability or journal-level fencing.

An [in-memory double-entry ledger](docs/architecture/ledger.md) demonstrates per-asset balanced integer postings, transaction-ID idempotency, and same-process concurrent retry serialization. It is not durable, fenced, or connected to matching; negative balances are permitted. Run `python3 -m unittest discover -s tests -p 'test_ledger.py' -v`.

An optional [protected-account balance policy](docs/architecture/ledger.md)
rejects overdrafts atomically within a single Ledger instance, including
concurrent spends. It is not a balance reservation or durable settlement
mechanism. Run `python3 -m unittest discover -s tests -p 'test_ledger_protected.py' -v`.

Local [balance reservation, release, and settlement](docs/architecture/ledger.md) are illustrated with [reservation tests](tests/test_ledger_reservations.py). Holds are in-memory only and do not survive restart.

Partial fill settlement keeps unfilled funds reserved and deduplicates fill IDs
within one process; see [partial fill tests](tests/test_ledger_partial.py).
This does not provide restart-safe settlement or distributed fencing.

Direct Ledger posts now reject reserved `reservation-settle:` and `reservation-fill:` transaction IDs, so callers cannot preempt internal settlement IDs. See [namespace regression tests](tests/test_ledger_namespace.py). This is an in-process API guard, not durable settlement or authorization.
