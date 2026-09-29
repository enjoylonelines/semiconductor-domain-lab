# Phase 5 Supervisor-loss backlog evidence

## Injection

A calibrated Heavy workload of 32 Runs was dispatched with eight bounded Supervisor containers. Six seconds after submission, `phase5-supervisor-1` was terminated with `SIGKILL`. Docker reported exit code 137 and `OOMKilled=false`.

## Result

The workload reached persisted terminal states in 53.958689 seconds:

- 31/32 Runs: `SUCCEEDED` and `TRUSTED`.
- 1/32 Runs: `FAILED` and `UNKNOWN`.

The killed Supervisor's Run did not become a trusted success. The other Runs continued to completion. This is one controlled same-VM fault observation; it does not prove multi-host recovery or automatic retry semantics.

## Decision

The observed result supports the fail-closed contract: a lost Supervisor cannot silently produce an accepted completion. The failed Run needs its durable termination witness and duplicate-accepted-completion query retained in a follow-up fault record before claiming full Cycle 1 closure.
