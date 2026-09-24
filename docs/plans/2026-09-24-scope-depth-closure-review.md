# EDA 프로젝트 범위·깊이·종료 검토

작성일: 2026-09-24  
기준 브랜치: `main` @ `bb4997b`

## 1. 현재 변경사항 검토

최근 구현은 timing report 파서/서비스의 완전성·provenance 보강에 더해 hardware adapter, replay client, JEV 적용 검토까지 확장됐다. 현재 작업 중 추적되지 않은 항목은 `uv.lock`뿐이며, 최근 커밋은 다음 흐름을 보인다.

- `bb4997b`: JEV completeness/provenance를 run에 보존
- `7ea8e56`: hardware data replay client 추가
- `95e727c`: SDK 설치 호환성 문서
- `ad3171c`: JEV 적용성 검토
- 기존 parser/service 경계, fixture adapter, benchmark, bounded load 증거가 이미 존재

문제는 기능 부족이 아니라 **핵심 포트폴리오 서사가 분산되는 것**이다. 현재 저장소에는 EDA report correctness, 하드웨어 SDK integration, JEV completeness, API/worker/load가 모두 존재한다. 이들을 동등한 주제로 계속 확장하면 “무엇을 깊게 해결했는가”가 흐려진다.

## 2. 프로젝트 대표 문제

대표 문제는 아래 하나로 고정한다.

> EDA 실행 결과와 timing report가 실패·누락·비유한 수치·포맷 차이 때문에 정상 결과로 오인되지 않도록, 실행 상태와 파싱 결과를 분리하고 원문까지 추적 가능한 검증 경계를 만든다.

이 문제는 공개 SW Engineer 업무의 반도체 로그/리포트 파싱·데이터 가공 자동화와 직접 연결된다. 회사 내부 병목을 재현했다고 주장하지 않는다.

## 3. 깊이 축

### 축 A — EDA report semantics

반드시 설명·검증할 범위:

- STA에서 report가 어떤 입력과 조건을 전제로 생성되는지
- slack, setup/hold, path 범위, 단위가 결과 해석에 어떤 영향을 주는지
- report 일부 값과 design 전체 판정을 구분하는 이유
- tool exit code, parse completeness, check result를 하나의 success flag로 합치면 안 되는 이유
- truncated/duplicate/unsupported-version report를 어떻게 판별할지

깊이는 “STA 용어를 안다”가 아니라 **원문 → parser → normalized model → service state → 저장 결과**를 역추적할 수 있는 수준으로 만든다.

### 축 B — long-running job correctness

parser correctness가 닫힌 뒤에만 두 번째 축으로 허용한다.

- HTTP 요청과 EDA 실행 수명 분리
- worker concurrency 제한
- timeout/cancel 시 child process 상태
- duplicate completion/retry의 idempotency
- DB 저장과 event/state transition 사이 실패
- at-least-once 처리에서 어떤 invariant를 보장할지
- queue/backpressure가 실제로 필요한 조건

Kafka/Redis 자체가 목표가 아니다. 현재 in-process worker가 어떤 실제 실패를 만들 때만 대안을 연다.

## 4. 현재 변경사항 중 유지/격리/중단

### 유지

- parser/service completeness·provenance 보강
- 실행 상태와 parse/check 상태 분리
- actual report fixture 확보 계획
- 실패·누락·비유한 숫자 반례
- bounded benchmark와 정확한 측정 조건
- software-only adapter boundary 자체

### 핵심 서사에서 격리

- JEV는 completeness/provenance 모델을 설명하는 보조 개념으로만 유지
- hardware SDK/replay client는 실제 EDA report 경로와 연결되는 경우에만 appendix/실험으로 남김
- SDK 설치 호환성은 환경 증거이지 대표 engineering claim으로 올리지 않음

### 추가 확장 중단

- 여러 vendor/format 동시 지원
- 전체 regression scheduler
- HPC/클러스터
- AI/LLM 기반 report 해석
- PPA 최적화, placement/routing, RTL 자동 수정
- 새 UI
- “100명 규모” 같은 가정 기반 scale feature

## 5. 수정 순서

### P0 — correctness closure

1. nonzero exit인데 `SUCCEEDED`가 저장되는 반례를 회귀 테스트로 고정한다.
2. parser가 유한 수치·단위·필수 필드를 검증한다.
3. service가 execution/parse/check를 분리해 상태를 보존한다.
4. truncated/unsupported/duplicate 조건을 명시적으로 거절하거나 UNKNOWN으로 남긴다.
5. 공개 실제 report 1개 계열을 확보해 synthetic fixture와 구분한다.
6. 원문 필드와 normalized result를 독립 oracle로 대조한다.

### P1 — bounded async depth

P0가 닫힌 뒤 아래 한 실험만 연다.

- 동일 run 요청/worker retry/timeout 중 하나를 골라 현재 lifecycle 실패를 재현
- baseline과 최소 대안을 동일 workload에서 비교
- 필요한 경우에만 idempotency key 또는 durable state transition을 도입

메시지 브로커 도입은 결과가 요구할 때만 결정한다.

## 6. 종료 조건

이 프로젝트는 아래가 모두 만족되면 종료한다.

- 실제 report fixture와 재현 명령이 있다.
- execution failure가 success로 저장되지 않는다.
- 지원 fixture의 필수 필드가 독립 oracle과 일치한다.
- unsupported/truncated/non-finite 결과를 정상 PASS로 승격하지 않는다.
- 한 개의 async failure mode를 재현하고 선택/비선택 이유를 설명할 수 있다.
- README 없이 15분 동안 STA report 의미 → parser → service → 실패 → 대안 → 검증 → 한계를 설명할 수 있다.

이후 새 기능은 포트폴리오 핵심을 강화하지 않는 한 추가하지 않는다.

## 7. 면접 방어 질문

- 왜 report parser가 단순 regex 문제가 아닌가?
- exit code, parse success, timing pass를 왜 분리했나?
- slack이 유한 숫자라고 해서 유효한 결과라고 볼 수 없는 이유는?
- 실제 report와 synthetic fixture를 어떻게 구분했나?
- FastAPI async endpoint만으로 long-running EDA job 문제가 해결되지 않는 이유는?
- duplicate completion이 들어오면 어떤 invariant가 깨질 수 있나?
- 왜 Kafka를 쓰지 않았거나, 어떤 증거가 생기면 쓰겠는가?

## 8. 다음 작업 1개

현재 계획대로 **nonzero exit false-success를 회귀 테스트로 고정하고 최소 상태 매핑을 수정한 뒤 실제 report fixture gate로 이동한다.** hardware/JEV 확장은 그 전까지 멈춘다.
