# EDA Run Orchestration Lab

OpenSTA 기반 정적 타이밍 분석(STA)을 **서버 작업으로 안전하게 실행·복구·검증하기 위한 백엔드 실험 프로젝트**입니다.

단순히 OpenSTA를 호출하는 데서 끝내지 않고, 장시간 CPU 작업을 여러 개 처리할 때 생기는 **실행 소유권, worker 손실, 중복 실행, PostgreSQL coordination, 결과 신뢰성**을 실제 부하와 장애 주입으로 검증했습니다.

> 이 프로젝트는 상용 EDA 시스템을 복제한 것이 아닙니다. 공개 OpenSTA와 고정된 실험 입력을 사용해 백엔드 실행 문제를 제한된 범위에서 검증한 프로젝트입니다.

## 한눈에 보기

| 항목 | 내용 |
| --- | --- |
| 문제 | worker가 사라져도 실제 OpenSTA 프로세스는 살아 있을 수 있어, 즉시 재실행 시 같은 분석이 중복될 수 있음 |
| 핵심 설계 | API와 실행 분리, PostgreSQL 실행 소유권, Supervisor 기반 실행 관리, Redis 진행 알림 |
| 검증 | 실제 OpenSTA 부하 / 장애 주입 / PostgreSQL coordination microbenchmark |
| 주요 결과 | worker-loss A/B에서 OpenSTA CPU 사용량 **-50.9%**, 실행 슬롯 4→8에서 처리량 **+25.5%**, DB claim 경로 인덱스 A/B에서 처리량 **+23.5%** |
| 현재 경계 | 동일 Docker VM의 logical host 검증까지. 물리 멀티호스트·상용 EDA·DB failover는 검증하지 않음 |

## Architecture

```text
REST API
   │
   ▼
PostgreSQL
- Run / Attempt 상태
- 실행 소유권
- atomic claim
- accepted completion
   │
   ├─────────────┐
   ▼             ▼
Host Agent A   Host Agent B
   │             │
   ▼             ▼
Supervisor     Supervisor
   └──────┬──────┘
          ▼
       OpenSTA

Redis Pub/Sub
└─ 실시간 진행 알림 전용
```

PostgreSQL을 최종 작업 상태의 기준으로 두고, Redis는 유실되어도 Run 결과에 영향을 주지 않는 **best-effort 진행 알림**으로 분리했습니다.

## Troubleshooting 1 — worker가 죽어도 분석은 살아 있었습니다

worker 종료를 곧바로 분석 종료로 판단하면, 기존 OpenSTA와 새 OpenSTA가 동시에 실행될 수 있습니다.

같은 SS Heavy 입력에서 다음 두 정책을 각각 5회 비교했습니다.

| 정책 | 총 OpenSTA CPU 중앙값 | 중복 실행 |
| --- | ---: | --- |
| worker 종료 직후 즉시 재실행 | **18.82 CPU-s** | 기존 분석과 약 9.03초 겹침 |
| 기존 실행 소유권 유지 | **9.24 CPU-s** | 새 분석을 시작하지 않음 |

현재 정책은 이 장애 경계에서 총 OpenSTA CPU 사용량을 **50.9% 낮췄고**, 장애 1회당 약 **9.4 CPU-s의 중복 연산**을 피했습니다.

- [실험 근거](docs/evidence/2026-09-30-worker-loss-duplicate-cost.md)
- [재시도 정책 결정](docs/decisions/2026-09-30-worker-loss-retry-policy.md)

## Troubleshooting 2 — 실행 슬롯을 늘리면 어디가 먼저 병목이 될까?

실제 OpenSTA 부하와 PostgreSQL coordination 부하를 분리해 측정했습니다.

### 실제 SS Heavy 실행

동일 Docker VM에서 실행 슬롯을 4개에서 8개로 늘렸을 때:

- 처리량: **0.396 → 0.497 Runs/s (+25.5%)**
- 전체 완료시간: **40.42 → 32.21초 (-20.3%)**

현재 환경에서는 OpenSTA CPU 실행 용량이 먼저 한계에 도달했습니다.

### PostgreSQL coordination

OpenSTA 연산을 제거한 별도 microbenchmark에서 32 workers × 1024 Runs를 반복했습니다.

인덱스 적용 후:

- 처리량: **189.7 → 234.3 Runs/s (+23.5%)**
- claim p50: **2.88 → 2.10 ms**
- lock wait: **13 → 6**
- p99은 오히려 악화된 구간이 있어 “모든 latency가 개선됐다”고 표현하지 않습니다.

현재 실제 EDA 처리량은 이 DB coordination 한계보다 훨씬 낮았기 때문에 Kafka를 추가하지 않았습니다.

- [PostgreSQL / multi-host evidence](docs/evidence/2026-09-30-multihost-and-postgres-coordination-limit.md)
- [PostgreSQL coordination decision](docs/decisions/2026-09-30-postgres-coordination-ceiling.md)
- [Kafka gate decision](docs/decisions/2026-09-30-postgres-delivery-kafka-gate.md)

## Result trust

프로그램이 종료됐다는 사실과 결과를 사용할 수 있다는 판단을 분리했습니다.

```text
process exit
   ↓
report parse
   ↓
analysis type / required fields validation
   ↓
timing result interpretation
   ↓
accepted result
```

실행 성공, 타이밍 기준 충족 여부, 리포트 신뢰성을 각각 다른 상태로 다룹니다.

## Tech Stack

- Python 3.11+
- FastAPI
- PostgreSQL
- Redis Pub/Sub
- Docker
- OpenSTA
- pytest

## Repository Guide

```text
src/eda_lab/        실행·상태 관리 핵심 코드
tests/              unit / contract / integration 테스트
benchmark/raw/      원시 benchmark 결과
docs/evidence/      측정 근거
docs/decisions/     설계 결정
docs/plans/         실험 계획과 종료 조건
```

## Run / Test

의존성은 `pyproject.toml`과 `uv.lock`을 기준으로 관리합니다.

```bash
uv sync
uv run pytest
```

멀티호스트 및 benchmark 실행은 각 compose 파일과 `tools/` 스크립트를 사용합니다.

## Scope & Limits

검증한 것:

- 실제 OpenSTA child process 실행
- worker-loss 장애 경계
- 실행 소유권 / fencing / accepted completion
- 동일 VM logical host 분리
- PostgreSQL atomic claim과 coordination 한계
- Redis progress 알림 분리

아직 검증하지 않은 것:

- 물리 서버 간 네트워크 장애
- PostgreSQL replication / failover
- 상용 EDA / license server
- 실제 sign-off MCMM workload
- autoscaling

실험 수치를 운영 환경 전체의 성능이나 비용 절감 수치로 일반화하지 않습니다.

## Why this project

이 프로젝트에서 가장 중요하게 본 것은 “기술을 많이 넣는 것”이 아니라 **실패를 재현하고, 실제 병목을 측정한 뒤 필요한 제어만 추가하는 것**이었습니다.

PostgreSQL이 실제 OpenSTA 실행을 충분히 공급하고 있는 동안에는 Kafka를 추가하지 않았고, worker가 사라졌다는 이유만으로 살아 있는 분석을 다시 실행하지 않았습니다.
