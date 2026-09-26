# PostgreSQL execution ownership fault-injection evidence

Date: 2026-09-26
Status: completed bounded Phase B verification
Raw record: [`2026-09-26-postgres-execution-ownership-faults.jsonl`](2026-09-26-postgres-execution-ownership-faults.jsonl)

## Scope

This is a same-host PostgreSQL/OpenSTA verification. A separate Python worker
process claims a durable Run, starts an actual OpenSTA child, and is then
terminated with `SIGKILL`. The test database is disposable and was truncated
before the full-suite run. It does not prove multi-host child liveness,
horizontal throughput, automatic re-execution, or production recovery.

## Commands and results

```text
EDA_POSTGRES_TEST_DSN=postgresql://…/eda_operational_test \
PYTHONPATH=src uv run python -W error::ResourceWarning \
  -m unittest discover -s tests -q

Ran 66 tests in 5.335s
OK
```

The fault suite ran an actual recorded OpenSTA fixture against PostgreSQL:

| case | injected boundary | observed durable outcome | invariant supported |
| --- | --- | --- | --- |
| B1 | kill worker after the child PID is persisted; leave child alive | reconciliation retained `RUNNING`; no attempt 2 was created | lease expiry alone does not authorize duplicate execution |
| B2 | confirm the same child dead, then reconcile | Run `FAILED`; attempt 1 `ABANDONED`; no automatic attempt 2 | dead-child recovery closes a stale Run without pretending success |
| B3 | OpenSTA emitted its report; worker killed before result persistence | Run `FAILED`; attempt 1 `ABANDONED`; metrics absent | an old/partial completion is not accepted |

Post-run database rows for B2 and B3 are recorded in the raw JSONL file. Both
have exactly one Attempt and the recovery classification
`worker_unavailable` / `recovery_required`.

## Decision and limit

For this bounded profile, confirmed-dead recovery ends the Run as `FAILED`.
Automatic whole-workload re-execution is not enabled: the current OpenSTA
workload has no checkpoint/resume contract, and a retry policy would need a
separate failure budget and Human Decision Gate. This closes Phase B only; it
does not open the PostgreSQL coordination benchmark or Kafka challenger.
