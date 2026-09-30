# Multi-host compute scaling and progress-event slice

Date: 2026-09-30
Base revision: db4967e
Status: closed. Logical multi-host compute scaling, container-operational evidence, and bounded Redis Pub/Sub progress delivery are implemented and verified. See `../evidence/2026-09-30-multihost-compute-and-redis-progress.md` and `../decisions/2026-09-30-multihost-compute-redis-progress.md`.

## Goal

Close the JD-facing execution slice after the PostgreSQL coordination cycle:

1. show that the supervised EDA architecture can consume additional execution compute across two independent logical Host identities;
2. record container-operational evidence and limitations;
3. add only the minimum Redis Pub/Sub slice needed for ephemeral progress delivery while PostgreSQL remains authoritative;
4. stop without opening Kafka, autoscaling, Kubernetes, or larger database stress.

## Capacity hypothesis

Available Docker VM: 8 physical/logical CPU budget visible to Docker.

Compare the same SS Heavy workload and provenance under:

- A: 1 logical Host × 4 Supervisors × 1 CPU each;
- B: 2 logical Hosts × 4 Supervisors each × 1 CPU each.

The comparison intentionally increases execution compute from four to eight CPU slots. It tests whether the architecture can use added execution capacity while preserving the same PostgreSQL ownership/fencing contract.

It does **not** prove:
- two physical machines,
- independent host failure domains,
- network partition behavior,
- production horizontal-scaling efficiency.

Prediction:
- B should materially increase throughput and reduce makespan versus A;
- each Host Agent must dispatch only to its own Supervisor pool;
- accepted completions remain one per Run;
- no expired live lease, recovery claim, UNAVAILABLE request, or provenance mismatch appears.

Falsification:
- added Host capacity does not improve throughput materially despite available CPU;
- backlog exists while Supervisor slots remain idle due to coordination;
- duplicate/stale accepted completion occurs;
- provenance or terminal correctness regresses.

## Workload

Use the already calibrated SS Heavy PicoRV32 x64 workload and fixed provenance.

Prefer 16 or 32 Runs per repeat so the 4-slot baseline contains multiple waves without turning this into a long capacity-characterization project. Repeat enough times to establish a median.

## Container evidence

Record:
- image revision / git revision;
- per-Supervisor CPU and memory limits;
- Host Agent dispatch budget;
- PostgreSQL profile;
- final Run/Attempt/execution-request states;
- Host distribution;
- makespan and throughput;
- provenance hashes;
- limitations.

## Redis Pub/Sub adoption gate

Redis is not a queue and not a source of truth.

Adopt only this bounded responsibility:

```text
PostgreSQL state transition
        |
        +--> best-effort progress event --> Redis Pub/Sub --> subscriber/UI
```

Contract:
- durable Run/Attempt state remains PostgreSQL;
- Redis event loss must not affect correctness;
- a reconnecting client reads PostgreSQL to recover current state;
- publisher failure must not fail the EDA Run;
- no replay/retention claim;
- no job delivery through Redis.

Minimum events:
- RUNNING / execution started;
- terminal SUCCEEDED or FAILED.

Test:
- subscriber receives live progress events;
- with subscriber absent, Run still completes;
- after subscriber reconnect, PostgreSQL provides authoritative current status.

## Stop condition

Stop when:
- logical multi-host compute scaling has a bounded repeated result;
- Redis progress delivery contract is covered by unit/integration evidence;
- container-operational architecture and limits are documented.

Do not add Kafka, autoscaling, Kubernetes, Redis queue/lock semantics, or more DB stress in this cycle.
