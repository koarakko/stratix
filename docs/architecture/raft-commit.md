# Raft current-term commit gate (educational)

`raft_commit_index(voters, acknowledgements, term=..., previous=..., log_terms=...)` builds on `quorum_commit_watermark` and applies Raft's **current-term commit rule**: a leader cannot advance its commit index based solely on a majority of older-term entries. A majority-replicated current-term entry may commit all preceding entries.

`log_terms` must cover every index from 1 to the majority candidate, with nondecreasing positive terms no greater than the leader's current term. Missing or extra entries, malformed terms, stale acknowledgements, and watermark regression fail closed. If the candidate is an older-term entry, the previous committed index is returned unchanged.

Run `python3 -m unittest discover -s tests -p 'test_raft_commit.py' -v`.

**Not production Raft.** Acknowledgements are unauthenticated and not tied to matching log hashes or durable fsync. This function does not provide election safety, log matching, membership changes, joint consensus, persistent commit state, fencing, or distributed split-brain prevention. The caller must enforce all of these; never use it as an authorization to settle real funds.

## Leader-log boundary validation

Optional `leader_last_index` checks every acknowledgement (including minority outliers) against the leader's last index and validates the entire contiguous leader term map, including the suffix after the quorum candidate. Invalid bounds, missing suffix entries, and future or decreasing terms fail closed. Without the argument, legacy candidate-prefix validation remains for compatibility. This is an index-range check, not authenticated log matching or durable acknowledgement verification.

Regression: `python3 -m unittest discover -s tests -p 'test_raft_commit_bounds.py' -v`.

## Strict log-index types

Python dictionaries consider `True`, `1`, and `1.0` equivalent keys. Every `log_terms` key must have exact type `int`; boolean, floating-point, and string indexes fail closed with `QuorumWatermarkError`. This validates input shape only; it does not authenticate the leader's log.

Regression: `python3 -m unittest discover -s tests -p 'test_raft_commit_index_types.py' -v`.

## Regression repair (2026-11-23)

The strict index-key check is now represented by real Python newlines rather than literal escaped `\\n` characters. This repairs a `SyntaxError` that previously prevented importing `raft_commit.py`. Run `python3 -m unittest discover -s tests -p 'test_raft_commit_regression.py' -v` for eight focused cases covering current-term commits, older-term rejection, empty logs, malformed index aliases, missing suffix, minority outliers and stable prior commits. The focused local run used reconstructed real replication modules; full-repository regression and post-push execution remain separate verification tasks. This is not durable log matching or leader fencing.
