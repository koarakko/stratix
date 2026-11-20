# In-memory fencing gate (educational)

`services.exchange.fencing.FencingGate` illustrates how a local write path can reject
commands from a stale leadership epoch. Install a token issued by an **external
linearizable authority**, then call `authorize(token)` immediately before a
protected operation. An epoch must strictly increase; reusing an epoch, even
with the same holder, is rejected. `revoke()` denies subsequent authorizations.

The gate tracks the highest epoch installed **within the process**, including
after `revoke()`. Reinstalling a revoked epoch (whether with the same or a
different holder) fails closed. A failed install leaves the active leader intact.
A new, higher epoch is required to resume after revocation.

The constructor requires a **trusted durable high-water mark**. A restarted
process must recover that mark before accepting any token. The in-memory
high-water mark is **not persisted by this class**: callers must durably record
an accepted epoch using an external, linearizable mechanism before treating it
as authoritative across restarts. This reference does not issue tokens,
authenticate holders, coordinate processes, atomically fence the storage layer,
or protect against a leadership change between authorization and a write.
It is **not safe for production trading** and is not yet wired into the
command journal or matching engine. Real fencing requires enforcing epochs
atomically at the durable write boundary.

Run `python3 -m unittest discover -s tests -p 'test_fencing.py' -v`.
