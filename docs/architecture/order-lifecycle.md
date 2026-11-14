# Order lifecycle projection (educational)

`services/exchange/lifecycle.py` derives immutable order states from the
**same committed command stream and execution snapshot**. It distinguishes
`open`, `partially_filled`, `filled`, and `cancelled` without assuming
that zero remaining quantity implies cancellation. A cancelled order preserves
its already-filled quantity and exposes its unfilled cancelled quantity.

`project_lifecycle(commands, executions)` rejects unknown execution order
IDs, overfills, duplicate placement IDs, duplicate/unknown cancellation, and
cancellation of fully filled orders. It is a **read-only projection** and does
not modify matching or order command processing. The projection assumes the
caller supplies a consistent committed snapshot; it does not validate
execution ordering against command ordering, prices, markets, or sides.

Run: `python3 -m unittest discover -s tests -p 'test_lifecycle.py' -v`.

This is an in-memory prototype, not a durable or replicated trading system.
There is no Raft, leader fencing, risk checking, ledger settlement, or funds
reservation. Next integrate this projection into `SequencedExchange` with
an atomic snapshot accessor and full repository regression tests.
