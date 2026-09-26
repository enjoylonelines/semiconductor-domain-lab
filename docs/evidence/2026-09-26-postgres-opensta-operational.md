# PostgreSQL(포스트그레스큐엘) operational-path(운영 경로) OpenSTA(정적 타이밍 분석 도구) evidence(근거)

## Scope(범위)

이 근거는 local host(로컬 호스트) 하나에서 central PostgreSQL 16 container(중앙 PostgreSQL 16 컨테이너)를 두고, 서로 독립된 two submitter process(두 제출 프로세스)와 two worker process(두 작업자 프로세스)를 실행한 integration(통합) 측정이다. 각 worker(작업자)는 최대 4개의 OpenSTA subprocess(하위 프로세스)를 실행해 shared admission budget(공유 입장 예산) 8개를 채웠다.

submitter(제출자)는 HTTP server(하이퍼텍스트 전송 프로토콜 서버)가 아니라 `JobService.submit()`을 직접 호출한다. 따라서 이 결과는 central database(중앙 데이터베이스) → queue claim(대기 작업 권한 획득) → independent worker(독립 작업자) → actual OpenSTA(실제 OpenSTA) 경로의 근거이며, network HTTP load(네트워크 HTTP 부하)나 multi-host deployment(다중 호스트 배포) 근거는 아니다.

## Contract(계약)

- API-side(응용 프로그램 인터페이스 측) submit(제출)은 immutable spec payload(불변 명세 적재)를 가진 `QUEUED` Run(대기 작업)만 기록한다.
- worker-side(작업자 측)는 PostgreSQL `FOR UPDATE SKIP LOCKED`로 Run(작업)을 하나만 claim(권한 획득)하고, Run/Attempt(작업/실행 시도)의 terminal state(종단 상태)를 기록한다.
- duplicate `job_id`(중복 작업 식별자)는 two submitter process(두 제출 프로세스)에서 한 Run(작업)으로 수렴한다.
- OpenSTA adapter-observed exit(어댑터 관측 종료), parser(파서), semantic validation(의미 검증), provenance(출처 추적), trust status(신뢰 상태)는 기존 SQLite path(라이트급 SQL 경로)와 같은 `JobService` 경로를 사용한다.

## Environment(환경) and workload(작업부하)

- host(호스트): 기존 single-host capacity evidence(단일 호스트 용량 근거)의 개발 장비, PostgreSQL은 Docker container(도커 컨테이너)
- database(데이터베이스): PostgreSQL 16, dedicated disposable test database(전용 일회성 테스트 데이터베이스)
- submitter(제출자): 2 process(프로세스), 총 요청 9개 = duplicate `job_id` 2개 + unique `job_id` 7개
- worker(작업자): 2 process(프로세스) × process-local OpenSTA concurrency(프로세스 로컬 OpenSTA 동시성) 4개
- actual work(실제 작업): recorded OpenSTA 3.1.0 fixed setup/max fixture(고정 setup/max 픽스처), unique Run(고유 작업) 8개
- repetitions(반복): 5회

## Result(결과)

| measurement(측정) | result(결과) |
| --- | --- |
| submitted requests(제출 요청) | 매 반복 9개 |
| unique Runs(고유 작업) | 매 반복 8개 |
| backpressured(역압 거절) | 0개; 예산 8개와 고유 Run 8개가 일치 |
| terminal Run status(종단 작업 상태) | 40/40 `SUCCEEDED` |
| trust status(신뢰 상태) | 40/40 `TRUSTED` |
| worker distribution(작업자 분배) | 매 반복 worker 1·2가 각 4개 완료 |
| elapsed p50(중앙 경과 시간) | 0.758941초 |
| elapsed p95(상위 95% 경과 시간) | 0.776502초 |
| submit latency p50(중앙 제출 지연) | 5.877ms, 45 submit samples(제출 표본) |
| submit latency p95(상위 95% 제출 지연) | 9.257ms |

Raw results(원시 결과)는 [JSONL](2026-09-26-postgres-opensta-operational.jsonl)에 있다. `created_or_existing=9`는 제출 응답 수다. duplicate request(중복 요청)도 같은 `QUEUED` Run(대기 작업)을 반환하므로, 새 Run 생성 수는 `unique_runs=8`로 별도 기록된다.

## TDD(테스트 주도 개발) and Test Scope Review(테스트 범위 검토)

첫 integration test(통합 테스트)는 PostgreSQL read(읽기)가 idle transaction(유휴 트랜잭션)을 남겨 advisory lock(자문 잠금) 대기에 걸리는 failure(실패)를 재현했다. `PostgresStore` read path(읽기 경로)를 autocommit(자동 커밋)으로 두고 mutation(변경)만 explicit transaction(명시 트랜잭션)으로 묶은 뒤 같은 test(테스트)를 Green(통과)으로 전환했다.

unit/contract(단위/계약): separate worker claim(분리 작업자 권한), shared budget(공유 예산), duplicate submit(중복 제출)을 PostgreSQL integration test(통합 테스트)로 확인했다. integration(통합): API-side submit(응용 프로그램 인터페이스 측 제출) → central DB(중앙 데이터베이스) → distinct worker(분리 작업자) → actual OpenSTA(실제 OpenSTA) 저장을 확인했다. regression(회귀): SQLite와 PostgreSQL을 합친 63-test suite(테스트 묶음)가 `ResourceWarning` error(자원 경고 오류) 조건에서 통과했다.

## Limits(한계) and decision gate(결정 관문)

이 결과는 one physical host(한 물리 호스트)와 fixed tiny workload(고정 작은 작업부하)에서 나온 것이다. HTTP server load(HTTP 서버 부하), remote database(원격 데이터베이스), connection pool(연결 풀), PostgreSQL restart(재시작), worker loss(작업자 손실), network partition(네트워크 분할), sustained arrival rate(지속 도착률), queue fairness(대기열 공정성), long-running netlist(장시간 넷리스트), license pressure(라이선스 압박)는 검증하지 않았다.

따라서 changed belief(갱신된 판단)는 **PostgreSQL operational path candidate(포스트그레스큐엘 운영 경로 후보)가 local multi-process(로컬 다중 프로세스) actual OpenSTA execution(실제 OpenSTA 실행)까지 연결됐음**이다. Human Decision Gate(사람 결정 관문)는 pending(대기)이다. 이 근거만으로 production adoption(운영 채택), Kafka(카프카), Redis(레디스), autoscaling(자동 확장)을 채택하지 않는다.

Project repository(프로젝트 저장소)가 source of truth(원본 기준)다. Career OS(커리어 OS)는 revision(리비전), 이 링크, 범위와 한계만 요약한다.
