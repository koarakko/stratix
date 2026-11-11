# ADR-0001: Prefer safety over write availability on quorum loss

- Status: Accepted for the reference design
- Date: 2026-11-12

## Context

A cryptocurrency exchange must avoid duplicated executions, inconsistent balances, and two independently writable matching engines. Region failures and network partitions make leader detection uncertain.

## Decision

- Use a **single authoritative writer per market** with monotonically increasing fencing epochs.
- A successful order-acceptance acknowledgement requires a durable record under the configured commit policy.
- A ledger entry must be idempotent and double-entry balanced; never infer a committed write from an API timeout.
- On loss of quorum, lease validity, or fencing authority, reject writes and surface an explicit unavailable/unknown result.
- Separate stateless regional API availability from stateful matching and ledger write availability.
- Measure and publish RTO, RPO, consistency checks and WAN latency rather than asserting "always available."

## Consequences

A regional failure may cause a temporary trading halt even if regional APIs remain reachable. This is intentional: preserving balances and order sequencing takes precedence over uninterrupted write acceptance. A cross-region synchronous quorum can increase order-acceptance latency. Operational failover must be gated on durable state reconciliation and fencing.

## Alternatives considered

- Uncoordinated active-active matching: rejected due to conflicting execution order.
- Async replication with automatic promotion: not selected as a zero-data-loss default because acknowledged writes may be lost.
- Quorum-based synchronous replication: target for experiments, but its performance and exact guarantees remain unverified.

## Verification plan

Add executable tests for duplicate request IDs, deterministic replay, double-entry conservation, stale-leader fencing, partitioned quorum, and regional recovery. Mark each property verified only after tests exist and pass.
