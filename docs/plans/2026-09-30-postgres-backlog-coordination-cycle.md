# PostgreSQL backlog / coordination bounded cycle

작성일: 2026-09-30  
상태: closed; evidence captured 2026-09-30  
선행 근거: [SS Heavy scaling and queued-lease closure](../evidence/2026-09-30-ss-heavy-scaling-and-queued-lease-fix.md)

## Problem

고정 8-Run batch에서는 SS Heavy OpenSTA 실행이 1/2/4/8 Supervisor로 정상 수렴했고,
8-Supervisor 지점에서도 PostgreSQL lock wait가 관측되지 않았다. 그러나 이것은 실행 capacity보다
빠르게 Run이 유입되어 backlog가 누적되는 경우의 coordination 한계를 검증하지 않았다.

이번 cycle의 질문은 하나다.

> 현재 PostgreSQL 기반 Run polling / atomic claim / state coordination 구조는 SS Heavy 실행 처리량보다
> 빠르게 작업이 유입되어 backlog가 누적될 때 어디까지 안정적으로 동작하며, Kafka 같은 별도 delivery
> layer가 필요한 한계가 실제로 관측되는가?

Kafka 도입 자체는 목표가 아니다.

## Fixed contract

다음은 실험 중 고정한다.

- SS Heavy input: PicoRV32 x64 calibrated Heavy netlist
- corner: `ss_100C_1v60`
- netlist SHA-256: `b3f09a42b23a9ff84c0084d4d284a9f8f5830b4c50f4972d68f59a18ea0938ce`
- Liberty SHA-256: `9b24f0db3967ac67b4cae1f74bb480fd47922d18d0ed577e3c121739b412c361`
- script SHA-256: `cad5237c39e914222b23d6f30a86c6c34d5782bad5480dc7c8714607fb2688a1`
- 8 independent Supervisors
- Supervisor당 1 CPU / 1.5 GiB
- 동일 Docker Linux VM: 8 CPU / 약 19.49 GiB
- PostgreSQL 16
- one Host Agent / supervised execution ownership contract
- application revision and container image revision

변경 변수는 arrival/backlog 크기뿐이다. 8 → 32 → 128을 기본 bounded 단계로 사용한다.
512/1,024는 앞 단계에서 coordination 한계가 불분명하고 실행 시간이 정당화될 때만 연다.

## Prior failure-mode contract

2026-09-30 선행 scaling에서 queued delivery가 Supervisor claim 전에 30초 lease를 넘기면서
정상 대기 작업이 `UNAVAILABLE`로 오판되는 결함을 발견했다.

현재 계약:

- delivery가 `QUEUED`인 동안 Host Agent session이 Attempt lease를 갱신한다.
- Supervisor가 `CLAIMED` 이후에는 Host Agent가 해당 Attempt lease 갱신 책임을 넘긴다.
- 이후 child 실행 중 lease/heartbeat 책임은 Supervisor다.
- stale recovery는 정상 queue wait를 worker loss로 오판하지 않는다.

Backlog 증가 시 이 correctness가 유지되는지를 성능 지표와 같은 우선순위로 검증한다.

## Metrics

### API / submission

- submit latency p50 / p95 / p99
- submission throughput
- request error
- idempotency conflict

### PostgreSQL coordination

- execution-request claim latency p50 / p95 / p99
- transaction failure / deadlock delta
- PostgreSQL lock wait sample maximum
- connection count maximum
- DB transaction rate proxy
- queued row 증가와 claim latency 관계
- 필요 시 claim candidate query `EXPLAIN ANALYZE`

### Queue / execution

- Run queue depth maximum
- delivery queue depth maximum
- queue wait p50 / p95 / p99
- backlog drain time / makespan
- active Supervisor execution slots / 8
- execution-slot utilization over sampled interval

### Correctness

- duplicate Attempt
- duplicate execution request
- duplicate accepted completion signal
- stale completion
- unexpected `UNAVAILABLE`
- lease/recovery failure
- non-terminal Run
- provenance hash mismatch

## Interpretation rule

queue wait 증가만으로 PostgreSQL 병목으로 판정하지 않는다.

다음과 같이 8 execution slots가 계속 사용되고, claim latency와 lock/connection pressure가 안정적이면
OpenSTA execution-capacity saturation으로 해석한다.

반대로 execution slot이 비어 있는데 delivery/claim 지연 때문에 채워지지 않거나, backlog 증가와 함께
claim latency, lock wait, connection pressure, DB transaction failure가 반복적으로 악화되면
coordination 한계 후보로 본다.

절대 production SLO는 만들지 않는다. baseline 대비 변화율과 재현 여부를 기록한다.

## Kafka challenger trigger — predeclared before result

### Performance trigger

동일 SS Heavy / 동일 8-slot capacity에서 다음 중 하나가 반복 관측되고 원인이 PostgreSQL
delivery/coordination 경로에 있음이 분리될 때만 연다.

- execution slot utilization이 coordination 지연 때문에 떨어진다.
- submit 또는 claim latency가 backlog 증가와 함께 구조적으로 악화된다.
- lock wait / connection pressure / transaction failure가 반복된다.
- queued-row 증가로 claim query 비용이 의미 있게 증가한다.

### Requirement trigger

성능과 별개로 다음 실제 요구가 생길 때만 연다.

- retained event
- replay
- independent multiple consumers
- consumer group delivery
- partition ordering
- large durable backlog가 제품 요구가 됨
- event reprocessing

현재는 위 요구가 기록되어 있지 않다.

## Stop condition

### Case A — PostgreSQL coordination limit not observed

최대 bounded backlog까지:

- accepted completion invariant 유지
- claim/submit coordination latency 안정
- lock/connection pressure 없음
- execution slots 정상 활용
- 병목이 SS Heavy CPU/resource 쪽으로 설명됨

이면 Kafka trigger 미충족으로 종료하고 Kafka를 구현하지 않는다.

### Case B — PostgreSQL coordination limit observed

동일 조건에서 재현되면:

1. OpenSTA execution saturation과 분리한다.
2. query/index/config 문제인지 확인한다.
3. 합리적인 PostgreSQL 수정은 한 번만 challenger로 허용한다.
4. 동일 workload를 재측정한다.
5. 그래도 delivery 책임 자체가 병목이면 Kafka bounded A/B를 연다.

Kafka는 delivery / partition / consumer group / redelivery만 담당하며,
PostgreSQL은 Run / Attempt / idempotency / ownership fencing / accepted completion / provenance의
authoritative source로 남는다.

## Explicit non-goals

- Heavy fixture 고도화
- 추가 PVT corner
- 16/32 Supervisor scaling
- autoscaling
- Kafka HA / KRaft tuning / Schema Registry / Kubernetes / multi-region
- physical multi-host throughput

multi-host correctness는 이 decision을 닫은 뒤 별도 Human Decision Gate로 남긴다.

## Human fields

- Human hypothesis: `unrecorded`
- Human prediction: `unrecorded`
- Human decision: `predeclared stop rule applied; final human review pending`
