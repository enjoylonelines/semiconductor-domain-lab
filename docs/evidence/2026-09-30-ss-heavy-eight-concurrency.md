# SS Heavy eight-concurrency validation

## Question (질문)

Does the 1.5 GiB admission candidate(입장 후보) remain sufficient when eight
SS(저속 코너) Heavy(고부하) OpenSTA children run concurrently in the bounded
same-VM container environment?

## Input and topology contract (입력과 구성 계약)

- One Docker Linux VM(도커 리눅스 가상 머신): 8 CPUs and 19.49 GiB total
  memory.
- One PostgreSQL 16 container, one SS Host Agent(호스트 에이전트), and eight
  independent SS Supervisors(감독자).
- Each Supervisor: one CPU, 1.5 GiB memory and memory-swap limit.
- Each batch: eight Runs(작업), each with one Attempt(실행 시도); three measured
  batches after a separate eight-Run input preflight(사전 확인).
- Every accepted Run recorded the SS Liberty SHA-256
  `9b24f0db3967ac67b4cae1f74bb480fd47922d18d0ed577e3c121739b412c361` and
  Heavy netlist SHA-256
  `b3f09a42b23a9ff84c0084d4d284a9f8f5830b4c50f4972d68f59a18ea0938ce` in
  provenance(출처 추적).

The first setup omitted `EDA_OPENSTA_SCRIPT_NAME` and
`EDA_OPENSTA_NETLIST_PATH`. It therefore ran the default tiny fixture in about
one second. That batch is explicitly rejected and retained as
`rejected-missing-heavy-runtime-config.json`; it is not included below. The
repaired configuration pins both variables and the preflight verified all
eight report provenance records before the measured batches began.

Raw observer output, all 24 terminal timing reports, and their SHA-256
manifest are versioned in `benchmark/raw/ss-heavy-8-concurrency-f2e289/`.

## Result (결과)

| measure(측정) | observed value(관측값) |
| --- | ---: |
| accepted terminal completion(승인된 종료) | 24/24 `SUCCEEDED/TRUSTED` |
| OOM kill(메모리 부족 종료) | 0/8 Supervisors |
| batch makespan(배치 완료 시간), median | 12.743 s |
| batch makespan, observer p95 | 13.182 s |
| throughput(처리량), median | 0.628 Runs/s |
| queue wait(큐 대기), median / observer p95 | 0.283 s / 0.425 s |
| PostgreSQL lock wait(잠금 대기), maximum | 0 |
| PostgreSQL connections(연결 수), maximum | 18 |
| Supervisor CPU(중앙 처리 장치), sampled peak | 100.69% of one-CPU cap |
| Supervisor memory(메모리), largest cgroup peak | 1,305,067,520 B |

The largest cgroup peak leaves 305,545,216 B (291.4 MiB, 19.0%) below the
1.5 GiB limit. The sampled CPU peak shows execution CPU saturation at the
per-Supervisor cap. It does not show a PostgreSQL lock contention limit in
this bounded batch.

## Decision, falsification, and limit (결정, 반증, 한계)

The 1.5 GiB SS Heavy admission candidate is accepted for this exact
eight-Supervisor same-VM profile. The earlier 12 GiB reservation arithmetic is
therefore now supported by one controlled eight-way observation, rather than
only by single-child arithmetic.

This does not establish a general worker-scaling curve: 1/2/4 SS Heavy points,
mixed corner workloads, sustained arrivals, timeout/cancellation under load,
physical multi-host capacity, and license-seat pressure were not measured.
One OOM, a non-terminal Run, a provenance hash mismatch, duplicate accepted
completion, or material queue/lock-wait regression in the same profile would
reject the admission setting and require remeasurement.

No Kafka expansion trigger fired here. The observed end-to-end limit is the
one-CPU execution cap, while PostgreSQL lock wait remained zero. Kafka is not
an adopted dependency from this result.
