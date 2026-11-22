# Ledger replay preflight size limit

`plan_ledger_replay(entries, *, max_commands=100_000)` rejects snapshots containing more than the configured number of commands. The positive integer limit is explicit and rejects booleans, floats and zero. This bounds the number of planned commands held in memory, not their byte size or the memory used by the source journal snapshot. The iterator is advanced once beyond the limit to detect overflow; no partial plan is returned. Existing valid snapshots up to the limit retain their original behavior.

The caller must use a verified `CommandJournal.entries()` snapshot. This preflight does not authenticate input, replay business transitions, enforce a memory quota, persist state or prevent split-brain. For larger historical logs, use an explicitly justified bound and design a separate checkpoint/snapshot recovery protocol.

Regression: `python3 -m unittest discover -s tests -p 'test_ledger_replay_limits.py' -v`. The local regression suite contains six tests covering the boundary, overflow, generators, invalid limits, empty input, and fail-closed behavior.
