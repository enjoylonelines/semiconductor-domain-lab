# Worker-loss duplicate execution cost evidence

Date: 2026-09-30
Base revision: `155e459`

## Question

If a worker disappears while the actual OpenSTA analysis is still alive, what is the compute cost of treating worker loss as tool loss and immediately starting the same analysis again?

The purpose is to produce a troubleshooting metric that matches the failure problem directly, rather than using only correctness counts such as "0 stale completions".

## A/B policy

Same SS Heavy PicoRV32 x64 input, same OpenSTA image, same 2 CPU / 4 GiB container budget.

### Naive immediate retry challenger

- start one SS Heavy OpenSTA process;
- inject the worker-loss decision boundary 0.5 s after launch, only while the process is confirmed alive;
- immediately start the same OpenSTA analysis again;
- let both processes finish.

This is a counterfactual benchmark harness, not application code.

### Current supervised ownership policy

- start the same SS Heavy OpenSTA process;
- inject the same worker-loss decision boundary;
- keep the already-running analysis because the surviving execution owner still owns it;
- do not create a second OpenSTA process.

## Results

Five valid repeats per policy.

| metric | immediate retry | current ownership policy |
| --- | ---: | ---: |
| median total child CPU time | **18.82 CPU-s** | **9.24 CPU-s** |
| median primary wall time | 9.53 s | 9.24 s |
| duplicate OpenSTA CPU time | **9.39 CPU-s / fault** | not launched |
| duplicate overlap window | **9.03 s / fault** | not launched |

Derived:

- avoiding immediate retry reduced total OpenSTA CPU consumption per injected worker-loss event by **50.9%**;
- the immediate-retry challenger spent a median **9.39 CPU-s** on the duplicate analysis;
- the two analyses overlapped for a median **9.03 s**.

The primary process itself remained approximately the same workload. The difference came from running the same CPU-heavy analysis twice.

## Interpretation

The failure problem is therefore not only "can a stale result be rejected?"

A worker-loss decision made without checking actual execution ownership can duplicate nearly one full SS Heavy analysis.

For this workload, preserving the surviving execution avoided about **9.4 CPU-seconds of duplicate analysis per worker-loss incident**.

This is the preferred portfolio metric because it directly expresses the operational cost of the failure mode.

## Validity and limits

Supported:

- actual SS Heavy OpenSTA execution;
- fixed input and container budget;
- process-level CPU time observed from child rusage;
- five repeats per policy;
- worker-loss decision boundary injected while the primary process was alive.

Not supported:

- production worker-loss frequency;
- annual infrastructure cost savings;
- physical host reboot or network partition;
- checkpoint/resume;
- licensed commercial EDA behavior;
- claim that all worker failures save exactly 9.4 CPU-s.

The number is workload-specific and should be presented as an experiment result, not a universal saving.

## Portfolio candidate

> worker 종료만 보고 즉시 재실행하면 기존 OpenSTA와 새 분석이 약 9.0초 겹쳐 실행되는 것을 재현했습니다. 실행 소유권을 분리해 기존 분석을 유지한 결과, SS Heavy 기준 장애 1회당 약 9.4 CPU-s의 중복 연산을 피하고 총 OpenSTA CPU 사용량을 50.9% 줄였습니다.

## Stop condition

Five valid repeats were collected for both policies and the primary portfolio metric is stable enough for this bounded workload.

Do not expand this cycle into additional fault classes or automatic retry policy design.
