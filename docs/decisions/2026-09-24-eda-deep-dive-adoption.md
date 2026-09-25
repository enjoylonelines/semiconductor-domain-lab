# EDA(전자 설계 자동화) deep-dive(심화 검토) adoption(채택) decision(결정)

작성일: 2026-09-24
결정자: 사용자 위임에 따른 구현 결정

## Adopted(채택)

- SQLite(라이트급 SQL 저장소) single-host(단일 호스트) durable Run/Attempt(지속 작업/실행 시도) 기록
- opaque lease token(불투명 임대 토큰), conditional heartbeat(조건부 심장박동), expired-lease reconciliation candidate(만료 임대 조정 후보)
- fixed-template OpenSTA subprocess(고정 템플릿 OpenSTA 하위 프로세스), timeout(시간 초과) termination(종료), explicit cancellation(명시 취소), input provenance hash(입력 출처 추적 해시)
- explicit in-flight budget(명시적 진행 중 실행 예산) backpressure(역압)
- strong Finding identity(강한 발견 항목 식별), fail-closed comparability(실패 안전 비교 가능성), and opt-in composite index(명시 선택 복합 인덱스)
- result correctness(결과 정확성)의 parse/semantic/provenance/trust axis(파싱/의미/출처 추적/신뢰 축) 분리

## Deferred(보류)

Kafka(카프카), Redis(레디스), PostgreSQL(포스트그레스큐엘), partitioning(파티셔닝), distributed fencing(분산 차단), and materialization(사전 계산)은 현재 실제 한계 실험에서 필요성이 관측되지 않아 도입하지 않는다.

## Revalidation trigger(재검증 조건)

다음 중 하나가 실제 workload(작업부하)에서 재현되면 해당 대안을 다시 연다: child process residue(하위 프로세스 잔존), single-host lease ownership ambiguity(단일 호스트 임대 소유권 모호성), sustained queue growth(지속 대기열 증가), in-flight budget rejection(진행 중 실행 예산 거절), SQLite write/index cost(라이트급 SQL 저장소 쓰기/인덱스 비용), retained replay(보존 재생) 또는 independent multi-consumer(독립 다중 소비자) 요구.

## Compute resource envelope(컴퓨팅 자원 경계)

server count(서버 수), CPU(중앙 처리 장치), memory(메모리), disk(디스크), license capacity(라이선스 용량)는 worker count(작업자 수)보다 먼저 명시·측정해야 하는 운영 입력이다. 2026-09-25에 측정한 개발 환경은 host(호스트) 1대, physical/logical CPU(물리/논리 중앙 처리 장치) 10/10, memory(메모리) 64 GiB, repository disk free(저장소 가용 디스크) 약 828 GiB다. 이 값은 배포 사양이 아니라 [고정 OpenSTA 단일 호스트 용량 실험](../evidence/2026-09-25-opensta-single-host-capacity.md)의 환경 경계다.

그 경계에서 fixed OpenSTA profile(고정 OpenSTA 프로파일)은 `max_workers=8`, `max_in_flight=8`, `resource_slots=8`을 채택한다. 같은 tiny workload(작은 작업부하)를 1/2/4/8 동시성에서 각 5회 실행해 8 동시성이 1 대비 평균 처리량 약 6.97배, p95 batch wall time(상위 95% 배치 경과 시간) 약 15.7% 증가를 보였다. 일반 `JobService` 기본값이나 다른 host(호스트)의 한도를 이 수치로 바꾸지 않는다.

resource profile(자원 프로파일)은 호스트별 명시 설정이다. CPU/memory quota(중앙 처리 장치/메모리 할당량), container limit(컨테이너 제한), license seat(라이선스 좌석), netlist size(넷리스트 크기), co-tenant workload(공동 실행 작업부하), queue/deadline requirement(대기열/마감 요구)가 바뀌면 1부터 같은 방법으로 재측정한다. 9개 이상 동시성·multi-host(다중 호스트)·autoscaling(자동 확장)은 한계 실험이 관측될 때만 다음 challenger(도전 대안)로 연다.

## Finding index(발견 항목 인덱스) 운영 정책

EDA(전자 설계 자동화) revision review(설계 버전 검토)는 한 번의 조회 횟수보다 revision(설계 버전)마다 발생하는 engineer comparison(엔지니어 비교)과 interactive latency(대화형 지연)가 중요하다. 따라서 index(인덱스)는 다음 세 조건이 모두 성립할 때만 해당 service profile(서비스 프로파일)에서 켠다.

1. `new-violations` comparison(새 위반 비교)이 실제 review workflow(검토 흐름)에 포함된다.
2. 동일 설계의 연속 두 revision batch(설계 버전 배치)에서 각각 Finding(발견 항목) 10,000개 이상이 수집된다. 이 값은 현재 측정된 workload(작업부하) 경계이며, production scale(운영 규모) 주장이 아니다.
3. 인덱스 없는 Q2 p95(상위 95% 조회 지연)가 250ms를 넘거나, revision batch(설계 버전 배치) 하나에 Q2 comparison(조회 2 비교)을 3회 이상 수행한다.

세 번째 조건의 3회는 현재 20,000 Finding(발견 항목) workload에서 단일 조회도 CPU time(중앙 처리 장치 시간)만 보면 인덱스 비용을 회수한다는 관측보다 보수적인 운영 기준이다. 이 기준은 단발 exploratory query(탐색 조회)가 index write/storage cost(인덱스 쓰기/저장 비용)를 영구히 만들지 않게 한다. 조건을 만족하지 않으면 기본값 `enable_new_violation_index=False`를 유지한다. 매 30일 또는 데이터 보존 정책 변경 시 write latency(쓰기 지연), database size(데이터베이스 크기), Q2 count(조회 2 횟수)를 다시 측정한다.

## Hardware resource(하드웨어 자원) 정책

TRACE32(트레이스32)·Aardvark(아드바크) 같은 장비는 단순 CPU slot(중앙 처리 장치 슬롯)이 아니다. resource key(자원 키)는 `adapter + physical device ID(물리 장치 식별자) + board/target configuration(보드/타깃 설정) + bus/probe mode(버스/프로브 모드)`로 구성한다. 같은 key(키)는 한 Attempt(실행 시도)만 소유한다.

1. preflight(사전 점검)는 장치 식별자, 연결, 승인된 firmware/target configuration(펌웨어/타깃 설정), 전원·reset ownership(리셋 소유권)을 확인한다. 확인 불가면 외부 command(외부 명령)를 보내지 않는다.
2. read-only diagnostic(읽기 전용 진단)은 transport failure(전송 실패) 뒤 제한 재시도를 허용할 수 있다. flash/write/reset/destructive operation(플래시/쓰기/리셋/파괴적 작업)은 결과가 불명확하면 자동 재시도하지 않는다.
3. timeout/cancel(시간 초과/취소) 뒤 close/release(닫기/반납)를 시도한다. 장치 state(상태)를 readback(다시 읽기)으로 확인하지 못하면 `UNKNOWN_HARDWARE_STATE`로 기록하고 quarantine(격리)한다. 해당 key(키)는 operator reset/inspection(운영자 리셋/점검) 전 새 작업을 받지 않는다.
4. heartbeat(심장박동)는 worker(작업자) 생존만 뜻한다. device health(장치 상태)나 target execution(타깃 실행)을 증명하지 않으므로, completion(완료)에는 별도 readback/artifact(다시 읽기/산출물) 근거가 필요하다.
5. raw transaction log(원시 트랜잭션 로그), device serial(장치 일련번호), board/firmware hash(보드/펌웨어 해시), command allowlist ID(명령 허용 목록 식별자), reset owner(리셋 소유자)를 provenance(출처 추적)에 남긴다. 비밀값·license path(라이선스 경로)는 남기지 않는다.

현재 구현은 fixture(고정 입력)와 injected-client boundary(주입 클라이언트 경계)에서 독점 acquire/release(획득/반납), destructive operation(파괴적 작업)의 unknown outcome(불명확한 결과) 격리, operator_id/inspection_id(운영자 식별자/점검 식별자)를 요구하는 명시 해제를 검증한다. 이 식별자는 아직 durable audit/provenance record(영속 감사/출처 추적 기록)로 저장하지 않는다. 실제 장비 연결·전기적 상태·readback(다시 읽기)·operator recovery(운영자 복구)는 real hardware(실제 하드웨어) 사용 승인 뒤 한 장비·한 read-only smoke command(읽기 전용 간이 명령)로 시작한다.

## Career OS(커리어 운영체제) 반영 시점

Career OS(커리어 운영체제)는 모든 딥다이브가 끝날 때까지 기다리는 원본 저장소가 아니다. 각 bounded cycle(제한된 사이클)이 plan(계획), implementation(구현), evidence(근거), decision(결정), limitation(한계)을 갖고 commit(커밋)된 뒤에만 짧은 link/summary(링크/요약)를 추가한다. 실행 중 원시 수치, 미확정 판단, 중간 변경은 Career OS(커리어 운영체제)에 적재하지 않는다. 이 저장소가 source of truth(원본 기준)로 남는다.

이 저장소가 source of truth(원본 기준)이며, Career OS(커리어 운영체제)는 이 문서와 evidence(근거)를 링크·요약만 한다.
