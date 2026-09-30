# Backlog startup migration deadlock — rejected evidence

Date: 2026-09-30  
Base revision: `9ad020a fix: retain queued execution leases`

## Status

**Rejected / invalid backlog evidence.**

The isolated SS Heavy backlog environment failed before it could be accepted as a PostgreSQL backlog-capacity measurement. The failure is preserved because it exposed a real coordination hazard, but it is not evidence that backlog volume itself requires Kafka.

## Environment recovered from Docker metadata

- image: `eda-ss-backlog:9ad020a`
- PostgreSQL: `postgres:16-alpine`, database `eda_backlog`
- one Host Agent: `ss-backlog-agent`
- eight Supervisors: `ss-backlog-supervisor-1..8`
- Supervisor limit: 1 CPU / 1.5 GiB
- Host Agent execution concurrency / in-flight cap: 8
- SS Heavy input:
  - corner: `ss_100C_1v60`
  - script: `picorv32x64_calibration.tcl`
  - netlist: `/phase5/picorv32x64_sky130hd.v`
  - Liberty: `/phase5/sky130_fd_sc_hd__ss_100C_1v60.lib`
- execution lease: 30 seconds
- supervised execution mode

## Observed failure

At 2026-09-30 07:37:27 UTC PostgreSQL reported a deadlock.

Operational statement:

```sql
UPDATE eda_execution_requests e
SET status='UNAVAILABLE'
FROM eda_attempts a
WHERE e.job_id=a.job_id
  AND e.attempt_no=a.attempt_no
  AND e.status IN ('QUEUED','CLAIMED','RUNNING')
  AND a.status='ABANDONED'
  AND NOT EXISTS (
    SELECT 1
    FROM eda_execution_witnesses w
    WHERE w.execution_id=e.execution_id
  )
```

Concurrent runtime initialization statement:

```sql
ALTER TABLE eda_execution_requests
ADD COLUMN IF NOT EXISTS process_pid integer
```

PostgreSQL reported:

- the operational UPDATE waiting for an `AccessShareLock`;
- the schema migration process waiting for an `AccessExclusiveLock`;
- the Host Agent transaction was aborted with `DeadlockDetected`.

The Host Agent then exited with code 1. Supervisor shutdown errors observed later were caused by administrator shutdown of the PostgreSQL container and are not separate accepted failure evidence.

## Root cause classification

This is **not yet a backlog-volume limit**.

`PostgresStore` performed schema migration from every process constructor. Starting worker / Host Agent / Supervisor processes therefore allowed DDL migrations to overlap with operational delivery/recovery statements.

The failure belongs to the database lifecycle boundary:

> schema migration and steady-state execution coordination were not separated.

It would be invalid to interpret this as `slowdown → Kafka`.

## Correction budget

Use the one permitted bounded PostgreSQL correction before considering Kafka:

1. keep automatic migration as the compatibility default for tests and existing callers;
2. add an explicit `python -m eda_lab migrate` bootstrap;
3. allow long-running worker / Supervisor processes to set `EDA_POSTGRES_AUTO_MIGRATE=0`;
4. for the backlog experiment, run migration exactly once before starting operational processes;
5. restart the same fixed eight-Supervisor SS Heavy topology;
6. rerun the same backlog stage before changing any other variable.

## Regression contract

Runtime processes with automatic migration disabled must not execute schema DDL on connection construction. Existing callers that do not opt out keep the current migration behavior.

## Decision

- preserve this run as rejected evidence;
- do not open Kafka;
- do not change Heavy, Supervisor count, VM resources, or PostgreSQL tuning;
- rerun the same condition after migration/runtime separation.
