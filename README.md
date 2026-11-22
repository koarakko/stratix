# stratix

Infrastructure for resilient digital asset exchanges.

> **Educational reference implementation — not production ready.**
> The trading components currently use in-memory state without persistence, consensus, durable balance reservation, durable ledger settlement, or leader fencing. Do not trade real assets or deploy them as a production exchange.

---

## Local Verification

Requires **Python 3.10+** (no AWS account needed). Run the full test suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

---

## Reference Components

### 1. Sequenced Exchange & Order Lifecycle

The sequenced order/matching reference includes an independently verified [lifecycle projection](docs/architecture/sequenced-exchange.md) covering `open`, `partially filled`, `filled`, and `cancelled` orders. It fails closed on any disagreement between the matching engine's remaining amounts and the projected state.

### 2. Command Journal & Recovery

A standalone [local checksummed command journal](docs/architecture/command-journal.md) illustrates append, `fsync`, idempotent retry, and fail-closed corruption detection. Its `entries()` accessor revalidates the on-disk journal before returning records.

- **Replay & Recovery**: A [versioned order-command codec](services/exchange/journal_codec.py) replays a verified journal into a new in-memory order state machine or, via `recover_exchange()`, reconstructs deterministic fills, remaining quantities, and order lifecycles in a new `SequencedExchange`. Recovery is read-only and fail-closed.
- **Cooperative POSIX Locking**: Appends serialize across cooperating POSIX writers using a persistent `<journal>.lock` sidecar (`flock`).
- **Scope & Limitations**: Not yet connected to the live matching engine, not a replicated commit log, and provides no atomic matching, consensus, power-loss durability guarantee, or distributed fencing.

<details>
<summary>Command Journal Regression & Fault-Injection Tests</summary>

| Focus | Description | Test File | Run Command |
| :--- | :--- | :--- | :--- |
| I/O failures | Short writes, `fsync` failures, and ambiguous recovery (does not simulate actual power loss) | [`test_journal_io_failure.py`](tests/test_journal_io_failure.py) | `python3 -m unittest discover -s tests -p 'test_journal_io_failure.py' -v` |
| Empty-journal deletion | Rejects deletion of an observed empty journal (not inode fencing or concurrent-writer safety) | [`test_journal_empty_file_deletion.py`](tests/test_journal_empty_file_deletion.py) | `python3 -m unittest discover -s tests -p 'test_journal_empty_file_deletion.py' -v` |
| File identity | Detects device/inode substitution for an open journal (not a multi-writer lock or fencing) | [`test_journal_inode_identity.py`](tests/test_journal_inode_identity.py) | `python3 -m unittest discover -s tests -p 'test_journal_inode_identity.py' -v` |
| Same-inode append race | Rejects external growth detected between validation and write (narrows race window; not TOCTOU proof) | [`test_journal_append_race.py`](tests/test_journal_append_race.py) | `python3 -m unittest discover -s tests -p 'test_journal_append_race.py' -v` |
| Sidecar locking | Serializes cooperating POSIX writers via `<journal>.lock` (not distributed fencing) | [`test_journal_lock.py`](tests/test_journal_lock.py) | `python3 -m unittest discover -s tests -p 'test_journal_lock.py' -v` |
| Lock identity | Detects sidecar replacement/deletion during lock acquisition before append | [`test_journal_lock_identity.py`](tests/test_journal_lock_identity.py) | `python3 -m unittest discover -s tests -p 'test_journal_lock_identity.py' -v` |
| Lock-holder termination | Verifies OS-terminated process releases advisory lock with committed bytes intact | [`test_journal_lock_crash.py`](tests/test_journal_lock_crash.py) | `python3 -m unittest discover -s tests -p 'test_journal_lock_crash.py' -v` |
| Read disappearance | Fails closed if pathname disappears after open (only initial `ENOENT` on unobserved journal is empty) | [`test_journal_read_disappearance.py`](tests/test_journal_read_disappearance.py) | `python3 -m unittest discover -s tests -p 'test_journal_read_disappearance.py' -v` |
| Lock descriptor cleanup | Failed sidecar `fstat` closes its descriptor and poisons the instance against unsafe retries | [`test_journal_lock_failures.py`](tests/test_journal_lock_failures.py) | `python3 -m unittest discover -s tests -p 'test_journal_lock_failures.py' -v` |
| Verified state | Ensures failed checksum/history verification does not advance trusted file metadata | [`test_journal_verified_state.py`](tests/test_journal_verified_state.py) | `python3 -m unittest discover -s tests -p 'test_journal_verified_state.py' -v` |
| Payload isolation | Verifies caller-owned nested payload mutations cannot alter committed history or break retries | [`test_journal_payload_aliasing.py`](tests/test_journal_payload_aliasing.py) | `python3 -m unittest discover -s tests -p 'test_journal_payload_aliasing.py' -v` |

</details>

### 3. Leadership Fencing Gate

An [in-memory leadership-epoch fencing gate](docs/architecture/fencing-gate.md) demonstrates rejection of stale and conflicting leaders, including restart high-water-mark checks.

- **Local Serialization**: `run_authorized` serializes leadership changes (`install` / `revoke`) within a single gate instance.
- **Reentrancy Protection**: Same-thread callback reentrancy checks prevent an authorized operation from replacing or revoking its own gate leader mid-callback.
- **Scope & Limitations**: Not integrated with storage or the command journal; provides **no distributed fencing or linearizability guarantee**.

| Focus | Description | Test File | Run Command |
| :--- | :--- | :--- | :--- |
| Epoch & high-water mark | Rejects stale and conflicting leaders | [`test_fencing.py`](tests/test_fencing.py) | `python3 -m unittest discover -s tests -p 'test_fencing.py' -v` |
| Operation serialization | Serializes local leadership changes with `run_authorized` | [`test_fencing_operation.py`](tests/test_fencing_operation.py) | `python3 -m unittest discover -s tests -p 'test_fencing_operation.py' -v` |
| Callback reentrancy | Blocks mid-callback `install()` / `revoke()` and nested calls | [`test_fencing_reentrancy.py`](tests/test_fencing_reentrancy.py) | `python3 -m unittest discover -s tests -p 'test_fencing_reentrancy.py' -v` |
| Threaded leadership | Verifies in-flight callback locking, stale rejection, and cleanup | [`test_fencing_threading.py`](tests/test_fencing_threading.py) | `python3 -m unittest discover -s tests -p 'test_fencing_threading.py' -v` |

### 4. In-Memory Double-Entry Ledger

An [in-memory double-entry ledger](docs/architecture/ledger.md) demonstrates per-asset balanced integer postings, transaction-ID idempotency, and same-process concurrent retry serialization.

- **Protected Accounts**: Optional `protected_accounts` configuration rejects overdrafts atomically within a single `Ledger` instance (including concurrent spends).
- **Reservation retry safety**: Only untouched active holds accept identical reserve retries; closed or partially filled reservation IDs are rejected.
- **Reservations & Partial Fills**: Supports local balance holds (`reserve`, `release`, `settle`, and `settle_partial`). Partial fills keep unfilled funds reserved and deduplicate fill IDs within one process.
- **Settlement Modes & Namespace Guard**: Full consumption by partial fills is distinct from a full-settlement retry (`settle()` rejects reservations already completed through fills). Direct `post()` calls reject reserved `reservation-settle:` and `reservation-fill:` transaction IDs.
- **Journal command codec**: A [strict versioned ledger command codec](docs/architecture/ledger-journal-codec.md) represents balanced funding postings and reservation/settlement operations, copying caller-owned posting lists on encoding; it does not persist or replay them.
- **Iterator initialization safety**: Replay preflight also rejects `OSError`, `RuntimeError`, and `ValueError` raised while constructing a journal iterator, before any Ledger mutation. Regression: `python3 -m unittest discover -s tests -p 'test_ledger_replay_iterator_init.py' -v`.
- **Ledger replay preflight**: [`plan_ledger_replay()`](services/exchange/ledger_replay_plan.py) validates a complete contiguous journal snapshot and converts commands to an immutable plan before any Ledger mutation. It does **not** execute commands, check business state, or guarantee recovery. Run `python3 -m unittest discover -s tests -p 'test_ledger_replay_plan.py' -v`.
- **Read-only audit**: `audit_transactions()` independently recalculates per-account/asset balances from a supplied transaction snapshot, rejects unbalanced or malformed postings, and can compare against an expected balance map. It does not verify snapshot authenticity, completeness, holds, or durable state.
- **Scope & Limitations**: In-memory only and not connected to matching; does not survive restart and provides no durable settlement, authorization, or distributed fencing.

| Focus | Description | Test File | Run Command |
| :--- | :--- | :--- | :--- |
| Core postings | Balanced integer postings, idempotency, and retry serialization | [`test_ledger.py`](tests/test_ledger.py) | `python3 -m unittest discover -s tests -p 'test_ledger.py' -v` |
| Overdraft policy | Atomic overdraft rejection for `protected_accounts` | [`test_ledger_protected.py`](tests/test_ledger_protected.py) | `python3 -m unittest discover -s tests -p 'test_ledger_protected.py' -v` |
| Reservations | Local balance reservation, release, and settlement | [`test_ledger_reservations.py`](tests/test_ledger_reservations.py) | `python3 -m unittest discover -s tests -p 'test_ledger_reservations.py' -v` |
| Partial fills | Idempotent partial reservation settlement and fill-ID deduplication | [`test_ledger_partial.py`](tests/test_ledger_partial.py) | `python3 -m unittest discover -s tests -p 'test_ledger_partial.py' -v` |
| Namespace guard | Rejects reserved `reservation-settle:` / `reservation-fill:` IDs in `post()` | [`test_ledger_namespace.py`](tests/test_ledger_namespace.py) | `python3 -m unittest discover -s tests -p 'test_ledger_namespace.py' -v` |
| Transaction audit | Recalculate balances and reject malformed or per-asset unbalanced snapshots | [`test_ledger_audit.py`](tests/test_ledger_audit.py) | `python3 -m unittest discover -s tests -p 'test_ledger_audit.py' -v` |
| Ledger/audit integration | Real reservations, fills, cancellation, retries, concurrency, and snapshot tampering | [`test_ledger_audit_integration.py`](tests/test_ledger_audit_integration.py) | `python3 -m unittest discover -s tests -p 'test_ledger_audit_integration.py' -v` |
| Multi-asset audit | Reconcile independent BTC/ETH postings and expected balances | [`test_ledger_audit_multiasset.py`](tests/test_ledger_audit_multiasset.py) | `python3 -m unittest discover -s tests -p 'test_ledger_audit_multiasset.py' -v` |
| Settlement modes | Distinguishes partial-fill completion from full-settlement retries | [`test_ledger_settlement_modes.py`](tests/test_ledger_settlement_modes.py) | `python3 -m unittest discover -s tests -p 'test_ledger_settlement_modes.py' -v` |

---

## Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Sequenced Exchange](docs/architecture/sequenced-exchange.md)
- [Command Journal](docs/architecture/command-journal.md)
- [Fencing Gate](docs/architecture/fencing-gate.md)
- [Double-Entry Ledger](docs/architecture/ledger.md)
- [ADR 0001: Consistency Before Availability](docs/adr/0001-consistency-before-availability.md)

---

## Long-Term Goal

The longer-term goal is a Terraform-based, multi-region AWS architecture with replayable matching, a double-entry ledger, recovery testing, and documented consistency trade-offs. **None of these aspirations is a production guarantee.**
