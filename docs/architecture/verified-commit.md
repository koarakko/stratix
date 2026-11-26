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

ACK digest input is checked with exact built-in types before comparison:
index zero requires `None` by identity; positive indexes require an exact
`str` containing 64 lowercase ASCII hexadecimal characters. This prevents
objects with custom equality methods from impersonating a valid digest.
All malformed values fail closed, including minority-voter reports.

Run `python3 -m unittest discover -s tests -p 'test_verified_commit_digest_types.py' -v`
for the additional digest-boundary tests. These checks do not authenticate
reports or prove durable persistence.

Voter report dictionary keys must be exact built-in `str` values before
membership comparison. This rejects non-string objects with custom `__hash__`
and `__eq__` methods that impersonate a configured voter. The check also
rejects extra malformed keys even if the honest majority is present.
Run `python3 -m unittest discover -s tests -p 'test_ack_voter_keys.py' -v`.
This is an input-shape check, not reporter authentication or durable ACK proof.

## Cross-layer regression

`python3 -m unittest discover -s tests -p 'test_verified_commit_integration.py' -v` exercises the actual `verified_commit_index` → `raft_commit_index` → `quorum_commit_watermark` path. It checks current-term-only advancement, preservation of the previous watermark, rejection of minority out-of-range/hash-mismatched/non-durable reports, missing voters, incomplete leader logs, and deterministic retry after failure. These are in-memory preflight tests, **not** proof of ACK authentication, fsync, leader fencing, or crash-safe consensus.

## Optional leader self-report check

Pass `leader_id="leader"` to require the named leader's supplied report to
acknowledge `leader_last_index` in the current term, with the same durable and
chain-hash checks applied to all reports. A missing, stale, underreported, or
malformed leader report fails closed, including when other voters form a majority.
Omitting `leader_id` retains legacy behavior for callers that have not yet
identified the leader explicitly.

Run `python3 -m unittest discover -s tests -p 'test_verified_commit_leader.py' -v`.
This only checks **caller-supplied assertions**, not leader identity,
authenticity, actual fsync, or fencing. The caller must bind `leader_id` to
an independently authenticated and fenced leadership epoch.


## Contiguous log-map validation

Both verified_commit_index and raft_commit_index validate a complete
1-based index map using its cardinality and a bounded-key scan. Keys must be
exact built-in integers, the map length must equal the advertised last index,
and every key must be within 1..last_index. For a Python dictionary, those
conditions prove that no index is missing or duplicated without constructing
a full set of every expected index.

The check uses **O(1) auxiliary memory** and O(n) scan time. A very large
advertised last index paired with a small map is rejected by the length check
before any range is traversed. The Raft term map and verified hash map are
checked independently; malformed or sparse input fails closed.

Run
`python3 -m unittest discover -s tests -p 'test_raft_log_contiguity.py' -v`
for large-bound, same-cardinality out-of-range, and valid-contiguous cases.
This is still an in-memory input preflight, not proof of an authenticated log,
durable storage, leader fencing, or production consensus.
