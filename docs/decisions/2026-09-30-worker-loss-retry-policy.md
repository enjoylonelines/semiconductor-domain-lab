# Worker-loss retry policy decision

Date: 2026-09-30

## Decision

Keep the current supervised ownership rule: worker/Host Agent loss alone does not authorize an immediate duplicate OpenSTA execution while the existing analysis is still owned and alive.

Do not add automatic immediate retry for this failure boundary.

## Evidence

Using the same SS Heavy workload, five repeats per policy:

- immediate retry: median total OpenSTA child CPU = **18.82 CPU-s**
- current keep-original policy: median total OpenSTA child CPU = **9.24 CPU-s**
- duplicate analysis itself consumed median **9.39 CPU-s**
- duplicate executions overlapped the original for median **9.03 s**
- total child CPU consumption was **50.9% lower** with the current ownership policy under this injected failure boundary.

## Why this metric is preferred

The troubleshooting problem is a resource-ownership problem. A correctness count alone does not show its operational cost.

The measured duplicate CPU time directly answers what happens if worker death is incorrectly treated as analysis death.

## Limits

The benchmark is a counterfactual A/B harness inside one containerized environment. It does not establish production incident frequency or monetary savings.

The current figure is specific to the SS Heavy workload and should not be generalized to commercial sign-off jobs.

## Reopen trigger

Revisit retry policy only if:

- checkpoint/resume becomes available;
- physical host failure prevents the existing execution owner from completing;
- measured recovery latency becomes more costly than duplicate compute;
- a workload-specific retry budget is defined.
