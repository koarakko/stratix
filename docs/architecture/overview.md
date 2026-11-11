# Stratix reference architecture (draft)

Status: **design proposal**, not production validated.

## Scope

Stratix is an educational, deployable reference implementation of a centralized digital-asset exchange. No real customer funds, private keys, or production trading should be used. Terraform modules and service implementations will be added incrementally.

## Logical components

```text
Clients
  -> Global ingress / health-aware routing
  -> Regional API / order gateways (stateless)
  -> Sequencer / matching engine (single writer per market)
  -> Durable ordered command log
  -> Double-entry ledger (idempotent postings)
  -> Read models / market data / reporting

Separate trust boundary:
  Wallet and custody services (not part of the initial executable scope)
```

## Regional topology (target, not yet implemented)

- ap-northeast-1 (Tokyo): primary candidate
- ap-northeast-3 (Osaka): failover candidate
- ap-northeast-2 (Seoul): optional independent quorum location, subject to measured latency, jurisdiction and costs

A region is a failure domain; an Availability Zone is a smaller failure domain. API active-active **does not imply** matching or ledger multi-writer. A proposed five-member quorum (2/2/1) can tolerate loss of either two-member region only if the surviving three members remain mutually reachable. WAN round-trip latency directly impacts synchronous commit throughput and tail latency. Do not claim RPO=0 until every externally acknowledged transaction is durably replicated to a surviving quorum and recovery tests prove it.

## Required invariants

1. Each market has at most one fenced, authoritative order sequencer at a time.
2. Acknowledged order acceptance is durably recorded before success is returned.
3. Every trade has a unique execution ID and deterministic replay outcome.
4. Ledger postings balance for each asset; retries cannot post twice.
5. If quorum or authoritative ownership cannot be proven, **reject new writes** rather than risk split brain.
6. Failover must never silently accept orders against stale balances.
7. A failed or timed-out request is **unknown**, not automatically rejected; clients use idempotency keys to reconcile.
8. Replay, failover and restore tests must compare order state, fills, balances and audit history.

## Proposed delivery sequence

1. Threat model, invariants, local deterministic model and tests.
2. Terraform baseline: network, IAM boundaries, regional ECS and observability.
3. Matching and ledger sample with deterministic replay and invariant tests.
4. Explicit single-writer failover, fenced leadership, replicated durable log.
5. Multi-region Terraform and controlled failure drills.
6. Benchmark p50/p99 latency, throughput, RPO/RTO and fault coverage.

## Non-goals for initial milestones

- Production-ready exchange or custody system
- Real-money deposits, withdrawals, or signing
- Claims of zero downtime or zero data loss without measured evidence
- Automatically deploying paid AWS infrastructure in CI

See [ADR-0001](../adr/0001-consistency-before-availability.md) for the consistency policy.
