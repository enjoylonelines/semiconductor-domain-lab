# Worker-loss duplicate execution cost benchmark

Date: 2026-09-30
Base revision: 155e459
Status: closed. Five valid repeats per policy completed. See `../evidence/2026-09-30-worker-loss-duplicate-cost.md` and `../decisions/2026-09-30-worker-loss-retry-policy.md`.

## Portfolio question

The troubleshooting claim is not merely that stale completion is rejected. The operational problem is that treating worker loss as tool loss can start a second CPU-heavy OpenSTA analysis while the first analysis is still alive.

The benchmark therefore measures the cost of that wrong recovery decision.

## A/B policy

Same SS Heavy PicoRV32 x64 input, same OpenSTA binary/image, same container budget.

A. naive immediate retry challenger
- start one SS Heavy OpenSTA process;
- inject the worker-loss decision boundary while the first OpenSTA process is confirmed alive;
- immediately launch the same OpenSTA analysis again;
- let both processes finish;
- measure duplicate process CPU time and overlap duration.

B. current supervised ownership policy
- start one SS Heavy OpenSTA process;
- inject the same worker-loss decision boundary while it is alive;
- do not launch a duplicate because the surviving Supervisor still owns the execution;
- let the original process finish.

The naive challenger is an explicit counterfactual benchmark harness, not application code.

## Metrics

Primary portfolio candidates:
- additional OpenSTA CPU seconds consumed per worker-loss incident;
- duplicate execution overlap seconds per incident.

Secondary:
- original execution wall time;
- total child CPU seconds;
- wall time from injected worker-loss boundary until original completion.

Use median over 5 repeats.

## Fixed environment

- SS Heavy PicoRV32 x64
- SS/100C/1.60V Liberty
- Supervisor/OpenSTA style container image
- container budget: 2 CPU / 4 GiB for both A and B
- fault boundary: 0.5 s after first OpenSTA launch, only if primary process is still alive

## Falsification / validity

Reject a repeat if:
- primary OpenSTA already exited before fault boundary;
- either process exits non-zero;
- provenance/input differs;
- process CPU usage cannot be observed.

## Scope

This measures avoidable duplicate compute caused by an immediate-retry policy. It does not measure physical host failure, network partition, checkpoint/resume, or production scheduler behavior.

## Stop condition

Five valid repeats per policy and one stable median portfolio metric. Do not expand to more fault classes or scheduler redesign.
