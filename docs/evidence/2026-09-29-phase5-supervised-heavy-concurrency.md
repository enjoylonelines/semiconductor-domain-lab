# Phase 5 supervised Heavy concurrency evidence

## Question

Under the bounded local validation environment, can independent Supervisor processes accept calibrated Heavy OpenSTA execution requests and converge every Run to one trusted terminal result as concurrency rises from 1 to 8?

## Environment

- One Apple Silicon Mac host; Colima Linux VM constrained to 8 CPU and 20 GiB RAM.
- One PostgreSQL 16 container (0.5 CPU, 384 MiB), one Host Agent, and 1/2/4/8 independent Supervisor containers.
- Each Supervisor: 1 CPU, 2 GiB memory, unique Supervisor ID; all target the same Host Agent identity.
- Workload: PicoRV32 x64 calibrated Heavy netlist with the pinned OpenSTA image and `picorv32x64_calibration.tcl`.
- This is same-VM container isolation. It does not demonstrate multi-machine horizontal scaling.

## Results

| Concurrent Heavy Runs | Elapsed seconds | Throughput (Runs/s) | Accepted terminal results |
| ---: | ---: | ---: | --- |
| 1 | 10.005409 | 0.099946 | 1/1 `SUCCEEDED` + `TRUSTED` |
| 2 | 10.494095 | 0.190583 | 2/2 `SUCCEEDED` + `TRUSTED` |
| 4 | 10.786045 | 0.370850 | 4/4 `SUCCEEDED` + `TRUSTED` |
| 8 | 12.663676 | 0.631728 | 8/8 `SUCCEEDED` + `TRUSTED` |

Submission latency ranged from 1.138 ms to 3.878 ms across the four single-batch measurements.

## Observed decision

The measured 1→8 range did not expose a failed completion, duplicate accepted completion, or an obvious PostgreSQL coordination ceiling. Keep PostgreSQL as the operational coordination candidate for this bounded cycle; this does **not** meet the Kafka expansion trigger.

## Limits and next falsification

Each point is one batch, so no p95, CPU utilization, peak RSS, database lock-wait, or statistically stable throughput claim is made. The fixed 8-CPU/20-GiB VM and the shared host agent are intentional constraints. Repeat runs with resource sampling and database wait metrics are required before claiming an operational capacity limit or comparing Kafka.
