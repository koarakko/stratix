# Committed log integrity (educational)

`services/replication/log_integrity.py` supplies a **hash-linked, contiguous**
command log for local fault-injection experiments. It does **not** implement Raft,
replication, durability, authenticity, or Byzantine fault tolerance.

Each entry contains a 1-based uint64 sequence, immutable `bytes` payload, previous
SHA-256 digest, and its own SHA-256 digest. The genesis link is 64 zeroes. The
digest commits to a versioned domain separator, fixed-width sequence, fixed-width
payload length, payload bytes and previous digest. `append` first validates the
existing history and returns a new tuple; `verify` rejects gaps, duplicates,
reordering, changed bytes, malformed hashes and broken links.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_log_integrity.py' -v
```

**Security boundaries:** SHA-256 links detect accidental or adversarial mutation
only when the expected trusted head digest is held separately. An attacker who
can rewrite the whole log and head digest can forge a consistent chain. No
signatures, trusted checkpoint, persistent fsync, canonical command serializer,
leader epoch, fencing, quorum, or crash-consistent storage exist here. The
payload is opaque bytes; callers must provide a canonical, versioned encoding.
Never use this as proof of consensus or safe financial settlement.

Next: connect committed order commands to the matching model with an explicit
single-writer adapter and verify replayed executions and cancellation results.
