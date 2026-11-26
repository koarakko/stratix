# Verified leader log to Raft commit (educational)

The verified leader-log commit wrapper connects log_integrity.verify and verified_commit_index. It first snapshots and checks the complete contiguous leader log, including the SHA-256 hash chain and payload bytes. Only then does it derive the index-to-hash mapping and evaluate per-voter durable ACK reports.

Reports use (term, index, chain_hash, durable). Index zero uses a null digest. The supplied log_terms must cover the entire leader log, and the existing Raft gate enforces the current-term commit rule. Invalid entries, missing log terms, truncated/reordered/tampered logs, hash mismatch, and non-durable reports fail closed. No commit decision is returned on error.

Run: python3 -m unittest discover -s tests -p 'test_verified_log_commit.py' -v

Limitations: The leader log is an in-memory snapshot. The hash chain does not authenticate a remote node, prove a follower fsync, verify term provenance, or prevent a compromised leader from inventing a chain. There is no distributed fencing, membership reconfiguration, network consensus, or persistence guarantee. Do not use this helper to authorize real-asset settlement.

## Optional leader self-report

Pass leader_id to require that the named voter report the complete verified local log in the requested current term. Missing or underreported leader self-reports fail closed even if follower ACKs otherwise form a majority. Omitting the argument preserves legacy behavior. The name is matched against caller-supplied voter reports; it is not authenticated, and this option does not provide distributed fencing.

## Snapshot iterator failure behavior

The wrapper materializes the supplied entries iterable exactly once before verifying or deriving hashes. Any ordinary Exception raised during iterator creation, iteration, or snapshot verification is wrapped as QuorumWatermarkError; partially yielded entries can never produce a commit candidate. KeyboardInterrupt, SystemExit, and other BaseException process-control signals propagate unchanged. Retrying requires a fresh iterable when the previous iterator was consumed or failed.

Run: python3 -m unittest discover -s tests -p 'test_verified_log_commit_iterator_exceptions.py' -v

## Bounded snapshot materialization

Before hash verification, the wrapper uses `materialize_log_snapshot()` to
bound the supplied iterable. Defaults are `max_entries=100_000` and
`max_payload_bytes=67_108_864` (64 MiB). Both parameters must be exact
nonnegative integers; zero permits only an empty snapshot or zero aggregate
payload. Callers may tune them for their workload, but increasing either value
increases the resource budget.

The materializer counts bytes-valued entry payloads before retaining each
entry. It reads at most one lookahead item after reaching the entry limit to
distinguish an exact-limit snapshot from an oversized one. On either limit
violation the wrapper raises `QuorumWatermarkError` and returns no commit
candidate. Ordinary iterator exceptions are normalized; process-control
`BaseException` subclasses propagate. A consumed or failed iterator must be
recreated for a retry.

These are entry-count and raw-payload-byte limits, not an exact RSS ceiling:
Python object, tuple, mapping, and hash-verification overhead are additional.
The wrapper remains an in-memory preflight, not durable consensus.

Run:
- `python3 -m unittest discover -s tests -p 'test_log_snapshot.py' -v`
- `python3 -m unittest discover -s tests -p 'test_verified_log_commit_snapshot_limit.py' -v`
