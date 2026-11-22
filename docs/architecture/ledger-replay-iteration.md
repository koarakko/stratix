# Ledger replay iteration failures

The read-only `plan_ledger_replay()` preflight now wraps `RuntimeError` and `OSError` raised while consuming a journal snapshot iterator as `LedgerReplayPlanError`. This ensures callers can handle those source failures through the same fail-closed validation error path. No partially accumulated plan is returned.

This does not change the expected source: callers must obtain entries from `CommandJournal.entries()`, which independently verifies on-disk history. The planner does not authenticate data, replay business state, persist balances, or provide leader fencing. Other arbitrary exceptions from caller-provided iterators are not normalized.

Regression: `python3 -m unittest discover -s tests -p 'test_ledger_replay_iteration.py' -v`. This is a reference implementation, not a production recovery path.
