# Operating profile correction(운영 프로필 보정) 계획

작성일: 2026-09-25  
상태: 실행 전 architecture correction(아키텍처 보정)

## 0. Problem(문제)

기존 SQLite(라이트급 SQL 저장소) 결과는 one host(한 호스트), one database file(한 데이터베이스 파일), fixed OpenSTA workload(고정 OpenSTA 작업부하)의 local validation profile(로컬 검증 프로필)만 다룬다. 이를 운영 DB 선택 근거처럼 읽으면 안 된다. 9개의 external submitter(외부 제출자) 실험은 same-host contention(동일 호스트 경합)과 admission budget(입장 예산)을 검증했지만, multi-host client/server database(다중 호스트 클라이언트/서버 데이터베이스) 부하테스트가 아니다.

## 1. Source register(근거 장부)

- [SQLite appropriate uses](https://www.sqlite.org/whentouse.html): SQLite(라이트급 SQL 저장소)는 local storage(로컬 저장소)와 low writer concurrency(낮은 작성자 동시성)에 적합하며, many concurrent writers(많은 동시 작성자) 또는 network-shared direct access(네트워크 공유 직접 접근)에는 client/server RDBMS(클라이언트/서버 관계형 데이터베이스)를 권한다.
- [PostgreSQL MVCC](https://www.postgresql.org/docs/current/mvcc-intro.html) 및 [explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html): multi-version concurrency control(다중 버전 동시성 제어)과 row/table lock(행/테이블 잠금)의 의미를 구현 전 계약 근거로 사용한다.
- 이 저장소의 OpenSTA evidence(근거): [single-host capacity](../evidence/2026-09-25-opensta-single-host-capacity.md), [cross-process budget](../evidence/2026-09-25-opensta-cross-process-budget.md), [cross-process idempotency](../evidence/2026-09-25-opensta-cross-process-idempotency.md).

## 2. Operating profiles(운영 프로필)

| profile(프로필) | 목적 | topology(구성) | database(데이터베이스) | 현재 판단 |
| --- | --- | --- | --- | --- |
| Local validation(로컬 검증) | parser/process/recovery 계약 개발 | host(호스트) 1대, service(서비스) 1개, external submitter(외부 제출자) 제한 실험 | local SQLite file(로컬 SQLite 파일) | 채택됨 |
| Operational candidate(운영 후보) | networked API(네트워크 API)와 multiple worker(복수 작업자) | API process(응용 프로그램 인터페이스 프로세스) 2개, worker process(작업자 프로세스) 2개, central database(중앙 데이터베이스) 1개 | PostgreSQL(포스트그레스큐엘) 1개 | 가설; 회사 사실 아님 |

두 번째 행의 숫자는 capacity promise(용량 약속)가 아니라 최소 multi-writer topology(최소 다중 작성자 구성)다. server count(서버 수), CPU(중앙 처리 장치), memory(메모리), license capacity(라이선스 용량), arrival rate(도착률)는 배포 전 실제 환경 값으로 대체해야 한다.

## 3. Required contract(필수 계약)

PostgreSQL challenger(포스트그레스큐엘 도전 대안)는 새 기능을 늘리지 않고 다음 계약만 SQLite baseline(라이트급 SQL 기준선)과 동일하게 구현한다.

1. immutable `job_id`(불변 작업 식별자)의 concurrent submit(동시 제출)은 Run(작업) 하나와 execution claim(실행 권한) 하나만 만든다.
2. `max_in_flight` admission budget(진행 중 실행 입장 예산)은 API/worker process(응용 프로그램 인터페이스/작업자 프로세스) 경계를 넘어 공유된다.
3. Attempt(실행 시도)의 lease token(임대 토큰)이 아닌 writer(작성자)는 terminal transition(종단 전이)을 못 한다.
4. Run/Attempt(작업/실행 시도), finding batch(발견 항목 배치), foreign key(외래 키)는 transaction rollback(트랜잭션 되돌리기) 뒤 부분 상태를 남기지 않는다.

## 4. Experiment(실험)과 decision gate(결정 관문)

동일 machine(동일 장비)에서 SQLite와 PostgreSQL을 각각 다음 fixed workload(고정 작업부하)로 실행한다.

- 2 API submitter(응용 프로그램 인터페이스 제출자) + 2 worker(작업자), unique job(고유 작업) 16개와 duplicate job(중복 작업) 4개
- shared budget(공유 예산) 8개, one injected stale token(한 번의 오래된 토큰 주입), one invalid bulk row(한 번의 무효 대량 행)
- 측정: accepted/rejected/duplicate execution count(수락/거절/중복 실행 수), terminal-state violation(종단 상태 위반), partial batch count(부분 배치 수), `database locked` 또는 serialization/deadlock error(직렬화/교착 오류), p50/p95 submit latency(중앙/상위 95% 제출 지연), p50/p95 batch ingest latency(중앙/상위 95% 배치 적재 지연)

### Prediction(예측)

SQLite baseline(라이트급 SQL 기준선)은 local profile(로컬 프로필)에서 정확성 계약을 지킬 수 있으나, multi-host topology(다중 호스트 구성)의 직접 공유 DB 근거가 없다. PostgreSQL challenger(포스트그레스큐엘 도전 대안)는 중앙 DB 계약을 만족해야 하며, 오류 없이 단지 더 복잡하다는 이유만으로 채택하지 않는다.

### Falsification(반증)

- PostgreSQL implementation(포스트그레스큐엘 구현)이 duplicate execution(중복 실행), stale terminal write(오래된 종단 쓰기), partial batch(부분 배치)를 만들면 기각한다.
- SQLite가 operational candidate topology(운영 후보 구성)를 네트워크 직접 공유 파일로 대체하는 방식은 테스트 성공 여부와 관계없이 기각한다.
- PostgreSQL이 같은 계약을 만족해도 실제 multi-host requirement(다중 호스트 요구)가 없고 운영 비용만 늘리면 운영 채택을 보류한다.

### Human decision gate(사람 결정 관문)

사람은 비교 표를 본 뒤 `local SQLite only(로컬 SQLite 전용 유지)`, `PostgreSQL operational path(포스트그레스큐엘 운영 경로 채택)`, `additional workload required(추가 작업부하 필요)` 중 하나를 선택한다. 이 계획은 Career OS(커리어 운영체제)가 아닌 이 저장소를 source of truth(원본 기준)로 둔다.

## 5. Stop condition(종료 조건)

동일 계약·부하의 SQLite/PostgreSQL raw evidence(원시 근거), 환경 제약, 구현·운영 비용, Human Decision Gate(사람 결정 관문)가 기록되면 멈춘다. Redis(레디스), Kafka(카프카), autoscaling(자동 확장), production deployment(운영 배포)는 이 비교의 범위가 아니다.
