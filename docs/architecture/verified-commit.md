# Verified commit preflight (educational)

`verified_commit_index` wraps the current-term Raft gate and checks supplied
per-voter reports `(term, index, chain_hash, durable)` against the leader's
complete contiguous chain-hash map. Index zero uses a null digest. A hash is
a lowercase 64-character SHA-256 hex string representing the *cumulative*
log chain, not just the entry payload.

All voters must report. Every report must declare durable persistence and
match the leader's chain hash at its acknowledged index. Missing hashes,
mismatched hashes (even from a minority), stale terms, missing voters and
non-boolean durability flags fail closed. The existing Raft gate also requires
a majority-replicated entry from the current term.

Run `python3 -m unittest discover -s tests -p 'test_verified_commit.py' -v`.

**Security boundary:** These are caller-provided assertions. The function
does not compute hashes, authenticate reporters, prove fsync, establish
leadership, fence old leaders, or prevent split brain. The caller must
independently verify the cumulative hash-chain construction and persistence
evidence before passing reports. This is not production consensus and must
not authorize real-asset settlement.
