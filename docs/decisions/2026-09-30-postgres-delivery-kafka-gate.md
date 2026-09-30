# PostgreSQL delivery decision after SS Heavy backlog stress

Date: 2026-09-30

## Decision

Retain PostgreSQL for Run backlog, execution coordination, authoritative state, ownership/fencing, accepted completion, and provenance in the currently validated SS Heavy profile.

Do not open a Kafka challenger in this cycle.

## Why

After separating schema migration from runtime process startup, the accepted 8, 32, and 128 Run stages kept the fixed eight SS Heavy execution slots fed without observed PostgreSQL lock wait, connection pressure, expired lease, recovery invocation, unexpected UNAVAILABLE, or completion correctness failure.

The 32 and 128 stages showed backlog while all eight execution slots remained occupied. The dominant limit remained fixed OpenSTA execution capacity.

The earlier PostgreSQL deadlock was traced to runtime schema DDL overlapping operational queries. It was handled with the one permitted PostgreSQL correction: explicit migration bootstrap plus runtime auto-migration disabled. It is not treated as a structural delivery-layer limit.

## Kafka trigger status

Performance trigger: not met.

Requirement trigger: not met.

No current requirement was established for retained event history, replay, independent multiple consumers, partition ordering, consumer-group semantics as a product requirement, or event reprocessing.

## Stop condition

Stop at 128 Runs. Do not execute 512/1024 only to extend CPU-bound queue duration.

Reopen the delivery decision only if a later workload reproduces coordination starvation, lock/connection/query pressure after reasonable PostgreSQL correction, or introduces an actual broker-oriented requirement.

## Next gate

Open physical/logical multi-host ownership and recovery validation as a separate bounded cycle. Kafka is not a prerequisite.
