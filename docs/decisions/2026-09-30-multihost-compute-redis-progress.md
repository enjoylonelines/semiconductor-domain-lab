# Multi-host compute and Redis progress decision

Date: 2026-09-30

## Decision

Keep the current PostgreSQL-authoritative supervised execution architecture.

Adopt Redis Pub/Sub only for best-effort live progress notification.

Do not move job delivery, ownership, replay, or durable state into Redis. Do not open Kafka, scheduler redesign, autoscaling, or Kubernetes in this cycle.

## Why

The fixed SS Heavy workload showed that additional execution compute is useful, but not linearly efficient under the current Host Agent dispatch model.

Comparing the same 16-Run workload:

- 1 logical Host × 4 one-CPU Supervisors: median **0.396 Runs/s**, **40.42 s**
- 2 logical Hosts × 4 one-CPU Supervisors each: median **0.497 Runs/s**, **32.21 s**

This is:

- **+25.5% throughput**
- **-20.3% elapsed time**

All measured Runs remained `SUCCEEDED/TRUSTED`, with completed execution requests, no expired live Attempts, and uniform SS Heavy provenance.

The best 8-slot repeat, with an even 8:8 Host split, reached **0.679 Runs/s**, about **+71.5%** over the 4-slot median.

The less balanced repeats were slower. Longer 32-Run observations showed the same relationship:

- 15:17 Host split → 0.581 Runs/s
- 16:16 Host split → 0.707 Runs/s
- 18:14 Host split → 0.600 Runs/s

Therefore the next observed scaling issue is Host-level dispatch imbalance, not PostgreSQL capacity.

## Redis responsibility

Redis Pub/Sub is accepted for this narrow responsibility:

```text
PostgreSQL authoritative state
        |
        +--> best-effort progress event --> Redis Pub/Sub --> UI/subscriber
```

The durable contract remains:

- Run / Attempt state: PostgreSQL
- ownership / lease / fencing: PostgreSQL
- accepted completion: PostgreSQL
- reconnect state recovery: PostgreSQL
- live notification only: Redis Pub/Sub

Redis publish failure is caught and does not fail the EDA Run.

No replay or retention guarantee is claimed.

## Verified behavior

- live subscriber receives `RUNNING` and terminal progress;
- no-subscriber execution still succeeds;
- reconnecting client recovers current status from PostgreSQL;
- Redis publisher failure does not change execution success;
- supervised terminal completion publishes after the PostgreSQL final write.

## Container operations

Runtime schema migration remains separated from steady-state execution.

Host Agents and Supervisors run with explicit CPU/memory budgets and stable Host identities. Each logical Host owns its own Supervisor pool.

This is a container-operation proof inside one Docker VM, not proof of two physical hosts.

## Next trigger

Reopen architecture work only if one of these becomes real:

1. a second physical compute host is available;
2. Host-level load imbalance materially limits a production-representative workload;
3. artifact/network/license constraints become the next measured bottleneck;
4. replay, retained events, independent consumers, or other broker-specific requirements appear.

Until then, the current project is closed at the intended JD-facing depth.
