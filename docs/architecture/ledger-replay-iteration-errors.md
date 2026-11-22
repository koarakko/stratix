# Ledger replay iteration error handling

`plan_ledger_replay(entries)` constructs an immutable replay plan only after the entire iterator has been consumed and all ledger commands validated.

Iterator failures (`OSError`, `RuntimeError`, `ValueError`, or `TypeError`) are converted to `LedgerReplayPlanError`. No partial plan is returned. The original exception remains available as `__cause__`. This covers common failures from on-disk record readers and custom iterators; it does not catch process termination or every possible exception type.

Run: `python3 -m unittest discover -s tests -p 'test_ledger_replay_iteration_errors.py' -v`.

This is only a local preflight helper: it does not authenticate journal entries, persist state, or provide distributed consensus/fencing.
