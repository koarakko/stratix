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
