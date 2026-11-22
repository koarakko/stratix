# Verified leader log to Raft commit (educational)

`verified_log_commit_index(voters, reports, *, term, previous, log_terms, entries)`
connects the existing `log_integrity.verify` and `verified_commit_index`
modules. It first snapshots and checks the complete contiguous leader log,
including the SHA-256 hash chain and payload bytes. Only then does it derive
the index-to-hash mapping and evaluate per-voter durable ACK reports.

Reports use `(term, index, chain_hash, durable)`. Index zero uses `None`
for the digest. The supplied `log_terms` must cover the entire leader log,
and the existing Raft gate enforces the current-term commit rule. Invalid
entries, missing log terms, truncated/reordered/tampered logs, hash mismatch,
and non-durable reports fail closed. No commit decision is returned on error.

Run: `python3 -m unittest discover -s tests -p 'test_verified_log_commit.py' -v`

**Limitations:** The leader log is an in-memory snapshot. The hash chain does
not authenticate a remote node, prove a follower fsync, verify term provenance,
or prevent a compromised leader from inventing a chain. There is no distributed
fencing, membership reconfiguration, network consensus, or persistence guarantee.
Do not use this helper to authorize real-asset settlement.
