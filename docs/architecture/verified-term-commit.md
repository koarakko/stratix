# Verified v2 term-bound Raft commit gate (educational)

The verified term-bound commit wrapper verifies the entire immutable v2 term-bound hash chain and derives both the leader's contiguous index-to-term mapping and its cumulative SHA-256 hashes from the same verified snapshot. It then invokes the existing verified_commit_index gate, which requires all voter reports, matching hashes, the supplied durable flag, and the current-term majority rule. The API deliberately accepts no external log_terms mapping.

Each report is (current_term, index, v2_chain_hash, durable_bool); index zero uses a null hash. The caller must supply the complete leader log from sequence 1. Corrupt or truncated leader chains, mismatched ACK hashes, non-durable reports, stale report terms, and malformed membership fail closed with QuorumWatermarkError. An old-term majority candidate cannot advance the committed index. Replaying an identical immutable snapshot is deterministic.

When leader_id is supplied, the named voter must also report the complete local log (index == len(entries)) in the requested current term. A missing, stale, underreported, or malformed leader report is rejected even if another set of reports would otherwise satisfy the quorum. This validates caller-supplied evidence only and does not authenticate identity.

Run: python3 -m unittest discover -s tests -p 'test_verified_term_commit.py' -v. No AWS resources are needed.

Limitations: The durable flag is only caller-supplied evidence, not a verified fsync. Reports are not authenticated and there is no network protocol, leader election, fencing, stable quorum configuration, crash-recovery proof, or production-grade Split-Brain prevention. The digest is an unkeyed integrity chain, not a signature. Legacy v1 log entries and hashes are not accepted and no migration is provided. Do not use this gate to authorize real settlement.

## Snapshot iterator failure behavior

The wrapper materializes the supplied entries iterable exactly once before verifying or deriving terms and hashes. Any ordinary Exception raised during iterator creation, iteration, or snapshot verification is wrapped as QuorumWatermarkError; partially yielded entries can never produce a commit candidate. KeyboardInterrupt, SystemExit, and other BaseException process-control signals propagate unchanged. Retrying requires a fresh iterable when the previous iterator was consumed or failed.

Run: python3 -m unittest discover -s tests -p 'test_verified_term_commit_iterator_exceptions.py' -v

## Bounded snapshot materialization

The v2 wrapper shares `materialize_log_snapshot()` with the v1 wrapper.
Defaults are `max_entries=100_000` and
`max_payload_bytes=67_108_864` (64 MiB); both are exact nonnegative integer
keyword arguments and may be tuned per call. Bytes-valued payloads count
toward the aggregate byte cap before an entry is retained.

The materializer performs one lookahead after the entry cap. An oversized
entry count or payload total fails closed with `QuorumWatermarkError`; no
partial snapshot can reach term/hash verification or produce a commit
candidate. Ordinary iterator failures are normalized while
`KeyboardInterrupt`, `SystemExit`, and other `BaseException` signals
propagate. Retries require a fresh iterable.

The caps bound entry count and raw payload bytes, not exact process RSS.
Python object and derived-map overhead remain additional, and this remains an
in-memory educational preflight rather than durable consensus.

Run:
- `python3 -m unittest discover -s tests -p 'test_log_snapshot.py' -v`
- `python3 -m unittest discover -s tests -p 'test_verified_term_commit_snapshot_limit.py' -v`
