# Term-bound log hash chain (v2, educational)

`services.replication.term_log` defines a separate v2 chain. `append_term(entries, term, payload)` returns a new immutable tuple; `verify_term_log(entries)` checks contiguous indices, nondecreasing positive uint64 Raft terms, immutable payload bytes, lowercase digests and all previous-hash links. The digest commits to a domain separator, uint64 sequence, uint64 term, length-prefixed payload and previous SHA-256 hash. The separate domain prevents accidental reuse of legacy v1 hashes.

Run `python3 -m unittest discover -s tests -p 'test_term_log.py' -v`.

This does **not** change v1 `LogEntry` or automatically migrate persisted logs. There is no migration path or authenticated proof that a supplied term corresponds to a genuine Raft election. A caller must explicitly opt in to v2, persist and fsync entries, authenticate ACKs, and fence stale leaders. `verified_log_commit_index` still consumes v1 entries and external `log_terms`; do not use it with v2 hashes without a dedicated integration. This is not production-ready and cannot authorize settlement.
