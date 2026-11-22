# Raft current-term commit gate (educational)

`raft_commit_index(voters, acknowledgements, term=..., previous=..., log_terms=...)` builds on `quorum_commit_watermark` and applies Raft's **current-term commit rule**: a leader cannot advance its commit index based solely on a majority of older-term entries. A majority-replicated current-term entry may commit all preceding entries.

`log_terms` must cover every index from 1 to the majority candidate, with nondecreasing positive terms no greater than the leader's current term. Missing or extra entries, malformed terms, stale acknowledgements, and watermark regression fail closed. If the candidate is an older-term entry, the previous committed index is returned unchanged.

Run `python3 -m unittest discover -s tests -p 'test_raft_commit.py' -v`.

**Not production Raft.** Acknowledgements are unauthenticated and not tied to matching log hashes or durable fsync. This function does not provide election safety, log matching, membership changes, joint consensus, persistent commit state, fencing, or distributed split-brain prevention. The caller must enforce all of these; never use it as an authorization to settle real funds.
