# Phase 5 Supervisor-loss backlog evidence

## Scope and precondition

This is a bounded same-VM Linux-container fault injection, not multi-host
recovery evidence. `tools/phase5_live_child_supervisor_loss.py` selects an
execution request only after `docker exec <supervisor> kill -0 <pid>` succeeds,
then records the Supervisor, PID, and observation time before issuing
`docker kill`.

The final four-Run calibrated Heavy OpenSTA batch recorded:

```json
{"supervisor":"phase5-supervisor-6","pid":30,
 "precondition":"docker exec supervisor kill -0 pid succeeded"}
```

This proves that the targeted child was alive immediately before its local
Supervisor was killed. It does not prove remote-host process liveness.

## Observed result

The four Run batch reached persisted terminal states in 30.580687 seconds.

- 3/4 Runs: `SUCCEEDED` and `TRUSTED`.
- 1/4 Runs: `FAILED` and `UNKNOWN`.
- The failed Run had exactly one Attempt:
  `ABANDONED`, `worker_unavailable`, `recovery_required`.
- Its execution request became `UNAVAILABLE`; it has no termination witness.
- Querying for jobs with more than one Attempt returned `0`.

The lost Supervisor therefore cannot create an accepted completion from a
child whose result it can no longer observe. The system does not auto-retry
this loss: a later retry remains an explicit policy decision.

## Root cause found during the experiment

Before the correction, recovery fenced the Run and Attempt but left an
unwitnessed `eda_execution_requests` row in `RUNNING`. Since Host Agent
dispatch capacity counts `QUEUED`, `CLAIMED`, and `RUNNING` deliveries, enough
such rows could permanently consume the bounded in-flight budget.

`finalize_recovery` now changes the associated delivery to `UNAVAILABLE` in
the same transaction that abandons the Attempt and fails the Run. Worker
startup additionally retires legacy unwitnessed deliveries whose Attempt is
already `ABANDONED`. `UNAVAILABLE` is deliberately distinct from `COMPLETED`:
the latter requires a Supervisor-recorded termination witness.

The correction was verified by the PostgreSQL integration suite and by a
second live-child injection after rebuilding the Host Agent image. The second
batch again produced one `FAILED/UNKNOWN` Run with an
`ABANDONED/worker_unavailable` Attempt and `UNAVAILABLE` delivery; its three
other Runs completed as `SUCCEEDED/TRUSTED`.

## Limits and decision

This establishes a fail-closed local-host contract: at-least-once execution is
possible, while a lost local Supervisor cannot produce an accepted completion
and cannot leave a bounded delivery slot permanently occupied. It does not
establish automatic retry, remote child termination, remote artifact recovery,
or multi-host liveness. Those remain the multi-host Cycle follow-up.
