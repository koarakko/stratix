# Quorum commit watermark (educational)

`services.replication.commit_watermark.quorum_commit_watermark` computes the highest log index reported by a strict majority of a **fixed** voter set in a single term. With four voters, three acknowledgements are required. A missing voter, duplicate member, stale term, malformed index, or regression from `previous` fails closed.

The required count is centralized in `strict_majority_size(n) = floor(n / 2) + 1`. The selected watermark is the corresponding order statistic (the required-th highest ACK index), so exactly half of an even-sized cluster can never advance the watermark. This helper validates an exact positive integer and rejects booleans, floats, and non-positive counts.

```bash
python3 -m unittest discover -s tests -p 'test_commit_watermark.py' -v
python3 -m unittest discover -s tests -p 'test_quorum_majority_properties.py' -v
```

The property suite exhaustively compares all ACK vectors for one through seven voters and indexes zero through three against the definition “at least a strict majority acknowledged this index”. It also checks odd/even quorum sizes, independence from mapping/member iteration order, and monotonicity when any single ACK advances.

This is only a pure calculation. The caller must authenticate voter identity, verify acknowledgements correspond to **durably persisted** matching log entries, enforce leader fencing, verify log-term ancestry, and persist the committed watermark atomically. The function must not be used as a Raft commit decision by itself: Raft additionally requires the leader's current-term commit rule. No network or AWS resources are created.

The core quorum boundary now rejects non-`str` acknowledgement dictionary keys before membership comparison. This prevents custom `__hash__`/`__eq__` objects from impersonating a configured voter, including when they replace a legitimate key. Tests cover spoofing, extra malformed keys, and deterministic retries. This is strictly input validation, **not** authentication or a durable persistence proof.

Membership must be an iterable of voter-name strings, not a scalar string/bytes/bytearray or a mapping. This prevents accidental expansion of `"abc"` into three independent voters, or silent interpretation of mapping keys as membership. Tuple and generator membership remain supported. This is an API-boundary guard, not membership authentication.

Membership iterators are fully materialized before quorum calculation. If iteration raises `TypeError`, `ValueError`, `RuntimeError`, or `OSError`, the calculation raises `QuorumWatermarkError` without returning a candidate. This also covers generators that yield some members and then fail; they cannot be treated as a smaller valid membership. This includes I/O errors while reading membership from a generator. Other unexpected exceptions are not normalized. A fresh generator is required for retries because generators are consumed. Run `python3 -m unittest discover -s tests -p 'test_commit_watermark_iterator_errors.py' -v` for the targeted checks.

## Optional local log upper bound

Callers may pass `max_index` (a nonnegative exact `int` no smaller than `previous`) to reject **any** ACK index exceeding the leader's independently verified local log end, including a minority report. Invalid bounds and out-of-range ACKs fail closed with `QuorumWatermarkError`; no candidate is returned. The default `None` preserves the previous unbounded calculation for existing callers, and is **not** a safe production default. The caller must obtain and verify the bound against the local durable log; this option does not authenticate ACKs, establish log identity, prove persistence, or prevent split brain. Run `python3 -m unittest discover -s tests -p 'test_commit_watermark_bounds.py' -v`.
