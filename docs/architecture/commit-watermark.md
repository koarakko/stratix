# Quorum commit watermark (educational)

`services.replication.commit_watermark.quorum_commit_watermark` computes the highest log index reported by a strict majority of a **fixed** voter set in a single term. With four voters, three acknowledgements are required. A missing voter, duplicate member, stale term, malformed index, or regression from `previous` fails closed.

```bash
python3 -m unittest discover -s tests -p 'test_commit_watermark.py' -v
```

This is only a pure calculation. The caller must authenticate voter identity, verify acknowledgements correspond to **durably persisted** matching log entries, enforce leader fencing, verify log-term ancestry, and persist the committed watermark atomically. The function must not be used as a Raft commit decision by itself: Raft additionally requires the leader's current-term commit rule. No network or AWS resources are created.
