# SS Heavy memory admission calibration

## Question (질문)

For one SS(저속 코너) Heavy(고부하) OpenSTA execution(실행), what cgroup
memory limit(메모리 제한) distinguishes an OOM(메모리 부족) failure floor from
a bounded admission candidate(입장 후보) with meaningful reserve(여유분)?

## Scope and method (범위와 방법)

This is a capacity observation for **one child per container**, not a
concurrency or throughput result. Each run used one CPU (`--cpus 1`) and an
equal memory and memory-swap cgroup limit. The container collected
`memory.events`, `memory.peak`, OpenSTA exit code, stdout, and host-observed
wall time. A valid run required both exit code zero and `EDA_LAB_REPORT_END`.

The measured input is the PicoRV32 x64 Heavy netlist, SHA-256
`b3f09a42b23a9ff84c0084d4d284a9f8f5830b4c50f4972d68f59a18ea0938ce`, with
the official Volare SKY130 HD SS Liberty from revision
`f2e289da6753f26157a308c492cf990fdcd4932d`, SHA-256
`9b24f0db3967ac67b4cae1f74bb480fd47922d18d0ed577e3c121739b412c361`.
The three-corner workload provenance is recorded in
[the PVT validation](2026-09-29-heavy-pvt-corner-validation.md).

The Docker Linux VM(도커 리눅스 가상 머신) used for this calibration reported
8 CPUs and 20,926,898,176 bytes (19.49 GiB). That VM setting describes this
test boundary; it is not a production host specification.

Raw logs and cgroup records are versioned in:

- `benchmark/raw/ss-memory-limit-f2e289/`
- `benchmark/raw/ss-memory-headroom-f2e289/`

## Result (결과)

Each point has three independent child executions. p95 wall time uses linear
interpolation over those three host-observed values.

| limit | valid runs | OOM-killed runs | maximum `memory.peak` | p95 wall time | interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| 1.000 GiB | 0/3 | 3/3 | 1,073,741,824 B | 7.321 s | insufficient |
| 1.125 GiB | 0/3 | 3/3 | 1,207,959,552 B | 8.070 s | insufficient |
| 1.250 GiB | 3/3 | 0/3 | 1,275,904,000 B | 9.465 s | passing floor only |
| 1.500 GiB | 3/3 | 0/3 | 1,275,899,904 B | 11.625 s | admission candidate |

At 1.250 GiB, the largest observed peak leaves 66,273,280 bytes (63.2 MiB,
4.9%) of limit headroom. It is therefore evidence of a transition out of the
failure floor, not a safe operating reserve. At 1.500 GiB, the largest peak
leaves 334,712,832 bytes (319.2 MiB, 20.8%).

## Decision (결정)

Adopt **1.5 GiB per SS Heavy child** as the bounded test admission
candidate(입장 후보). This is a resource reservation for the current
single-child container profile, not an assertion that every SS workload or
future PDK release fits this limit.

An eight-slot test budget would reserve 12 GiB (8 × 1.5 GiB) from the measured
19.49 GiB VM, leaving about 7.49 GiB for PostgreSQL, Host Agent(호스트 에이전트),
container runtime, and the operating system. The existing eight-CPU cap stays
in place. This arithmetic is a **capacity-budget inference**, not evidence
that eight SS Heavy children can run concurrently without OOM or latency
regression.

## Prediction, falsification, and stop condition

- **Prediction(예측):** a single SS Heavy child at 1.5 GiB completes with a
  valid report and without `oom_kill` under this pinned input and VM profile.
- **Falsification(반증):** any validly staged repeat at 1.5 GiB that is OOM
  killed, lacks the terminal report marker, or exits nonzero rejects this
  admission candidate until the workload or limit is re-measured.
- **Stop condition(종료 조건):** this record stops after the one-child
  threshold and reserve measurement. It does not launch an eight-way run,
  change runtime defaults, claim a scaling result, or create a Kafka trigger.

The next separate experiment must run the chosen concurrent-slot profile with
the same SS input and measure end-to-end makespan, p95 queue latency, cgroup
OOM, CPU saturation, and PostgreSQL coordination wait. Only that experiment
can accept or reject the eight-slot budget as an operational setting.
