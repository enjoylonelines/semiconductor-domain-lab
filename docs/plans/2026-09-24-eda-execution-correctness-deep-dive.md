# 첫 번째 EDA(전자 설계 자동화) 딥다이브 보강 계획서

작성일: 2026-09-24
선행 근거: [범위·깊이·종료 검토](2026-09-24-scope-depth-closure-review.md), [실제 STA(정적 타이밍 분석) 증거](../evidence/2026-09-24-real-sta/README.md), [비동기 수명주기 증거](../evidence/2026-09-24-async-lifecycle-cycle.md), [통합 플랫폼 계약](../architecture/integration-platform-contracts.md), [AI 보조 엔지니어링 작업 방식](../engineering/ai-assisted-engineering-workflow.md)

## 1. 문제와 범위

### 대표 문제

실제 EDA(전자 설계 자동화) 실행에서 도구 결과가 생성된 뒤 작업자 손실, 시간 초과, 취소, 중복 전달, 자원 경합이 발생해도, 어떤 실행이 실제로 수행됐는지와 어떤 결과가 신뢰 가능한지를 보존한다. 특히 실제 하위 프로세스의 상태를 단순 호출자 시간 초과나 추측으로 단정하지 않는다.

첫 번째 딥다이브의 범위는 **EDA execution correctness(EDA 실행 정확성) + resource-aware async execution(자원 인지 비동기 실행) + failure recovery/reconciliation(실패 복구/조정)** 이다.

### 도메인·업무 환경 근거

Yosys(합성 도구)와 OpenSTA(정적 타이밍 분석 도구)는 짧은 HTTP API(응용 프로그래밍 인터페이스) 호출이 아니라 외부 subprocess(하위 프로세스)로 수행하는 long-running workload(장시간 실행 작업)다. 실행 시간, CPU(중앙 처리 장치)·Memory(메모리) 점유, report artifact(보고서 산출물)는 입력과 flow(흐름)에 따라 달라질 수 있으므로 async I/O(비동기 입출력)만으로 동시 실행을 늘리는 것은 자원 정책이 아니다. 도구 종료, report(보고서) 생성, parser(파서) 수용, 설계 check(검사), DB state(데이터베이스 상태)는 서로 다른 관측이며 부분 실패에서 불일치할 수 있다.

반복 분석 run(실행)에서는 같은 설계·제약·도구 조건을 다시 확인할 수 있어야 하므로 실행 이력과 provenance(출처 추적)가 필요하다. 저장소의 공개 업무 근거 J0/J2/J3/J4는 API(응용 프로그래밍 인터페이스), 비동기 메시지, RDB(관계형 데이터베이스), Redis Pub/Sub(레디스 발행/구독), 반도체 로그·리포트 파싱, 컨테이너 운영, migration(마이그레이션), CI/CD(지속적 통합/지속적 배포), HW(하드웨어) 협업을 연결한다. 이것은 EDA workflow(EDA 작업 흐름)에 적용할 engineering requirement(엔지니어링 요구사항)를 도출하는 근거이며, 회사 내부가 동일한 worker(작업자)·queue(대기열)·DB schema(데이터베이스 스키마)를 사용한다는 주장이 아니다. 세부 근거와 한계는 [출처 장부](../references/source-register-2026-09-23.md#채용-근거)를 따른다.

### 선행 근거와 이번 경계

- OpenSTA(정적 타이밍 분석 도구) 3.1.0의 고정 setup/max(최대 지연) 보고서 두 개를 실제 입력으로 파싱·정규화한 선행 슬라이스가 있다. `exit=0`인 타이밍 위반도 execution status(실행 상태)는 성공이고 check status(검사 상태)는 실패로 보존한다.
- 이전 synthetic(합성) 수명주기 슬라이스는 attempt-start(실행 시도 시작) 기록과 같은 프로세스 안의 stale-run reconciliation(오래된 작업 조정)을 검증했다. 실제 운영체제 하위 프로세스, 재시작 뒤 소유권, lease(임대), 실제 도구 자원은 검증하지 않았다.
- 이번 계획은 선행 결과를 다시 만들거나 모든 EDA 흐름을 일반화하지 않는다. 하나의 고정 OpenSTA/Yosys(합성 도구) workload(작업부하), 하나의 작업자 유형, 하나의 durable store(지속 저장소) 후보를 대상으로 실행 경계와 복구 불변식을 검증한다.

### 명시적 제외 범위

- 다중 벤더 보고서, hold(최소 지연), multi-corner(다중 코너), P&R(place and route, 배치·배선), 분산 스케줄러, 고가용성, 자동 확장, Kubernetes(쿠버네티스), 새 사용자 화면은 포함하지 않는다.
- Kafka(카프카), Redis(레디스), PostgreSQL(포스트그레스큐엘)는 기본 구현 항목이 아니다.
- 실제 라이선스 풀의 생산 규모, 여러 호스트의 fencing(소유권 차단), 대규모 처리량은 측정 전 주장하지 않는다.

## 2. 작업 방식과 Human Decision Gate(사람 결정 관문)

- Observed problem(관측된 문제): 실제 하위 프로세스에 대한 durable ownership(지속 소유권), 종료 확인, 복구·재시도 판단의 근거가 아직 없다. 현재의 in-process(동일 프로세스) 증거는 이 한계를 명시한다.
- Human hypothesis(사람 가설): unrecorded(기록되지 않음).
- Prediction(예측): unrecorded(기록되지 않음). AI/challenger hypothesis(AI/도전 가설)는 아래 판별 실험에만 기록한다.
- Decision required(필요한 결정): 동일 실행 경계에서 얻은 증거를 본 뒤, 사용자가 (a) 최소 영속 상태와 lease(임대) 규칙을 채택할지, (b) orphaned attempt(고아 실행 시도)를 자동 재시도할지 명시 재제출로 둘지, (c) challenger(도전 대안)를 열 조건을 결정한다.
- Changed belief(변경된 판단): pending human decision(사람 결정 대기).

이 계획은 계획서이며, 구현·실제 도구 실행·배포·Career OS(커리어 운영체제) 갱신을 승인하거나 수행하지 않는다.

## 3. 실제 workload(작업부하)와 execution boundary(실행 경계)

### 고정 workload(작업부하)

입력은 저장소의 `docs/evidence/2026-09-24-real-sta/`에 있는 tiny RTL(레지스터 전송 수준) 회로, Yosys(합성 도구) 스크립트, mapped netlist(매핑된 넷리스트), Sky130 Liberty(셀 라이브러리), normal/tight SDC(설계 제약)와 OpenSTA(정적 타이밍 분석 도구) Tcl(명령 언어) 프로파일이다.

두 조건을 함께 사용한다.

| 조건 | 기대 execution status(실행 상태) | 기대 check status(검사 상태) | 목적 |
| --- | --- | --- | --- |
| normal SDC(정상 설계 제약) | 성공 | 통과 | 정상 경로와 원문·정규화 결과 연결 |
| tight SDC(엄격 설계 제약) | 성공 | 실패 | 타이밍 위반을 실행 실패로 오인하지 않는지 확인 |

Yosys(합성 도구)는 입력 fixture(고정 입력) 생성의 재현 근거다. 매번 합성을 제품 실행 경로에 포함할지 여부는 이 딥다이브의 결정 대상이 아니다. 주 실행은 고정 netlist(넷리스트)와 OpenSTA(정적 타이밍 분석 도구) 한 번이다.

### 실행 경계

1. API(응용 프로그래밍 인터페이스)는 승인된 command template(명령 템플릿) 식별자와 검증된 매개변수만 받아 Run(작업)을 만든다. 임의 shell(셸) 문자열은 받지 않는다.
2. admission control(입장 제어)은 resource key(자원 키)와 동시 실행 한도를 확인한 뒤 Attempt(실행 시도)를 durable store(지속 저장소)에 `ACQUIRING`으로 기록한다.
3. worker(작업자)는 lease(임대)를 획득한 뒤 전용 work directory(작업 디렉터리)에서 OpenSTA(정적 타이밍 분석 도구) child process(하위 프로세스)를 시작한다. process ID(프로세스 식별자), start identity(시작 식별 정보), 명령 템플릿 식별자, 입력·설정 hash(해시), 도구 버전과 lease owner(임대 소유자)를 Attempt(실행 시도)에 기록한다.
4. 종료 뒤에만 stdout/stderr(표준 출력/표준 오류), exit code(종료 코드), report artifact(보고서 산출물), 파일 hash(해시)를 수집하고 parser(파서)와 checker(검사기)를 실행한다.
5. terminal transition(종단 전이)은 conditional update(조건부 갱신)로 한 번만 기록한다. Run(작업)의 실행·파싱·검사 상태는 분리한다.
6. 어떤 네트워크 응답, worker loss(작업자 손실), reconciler(조정기)도 도구의 정상 종료 증거 없이 Run(작업)을 `SUCCEEDED`로 만들 수 없다.

## 4. Run(작업)과 Attempt(실행 시도) 모델

| 모델 | 안정성·소유자 | 주요 필드 | 전이 규칙 |
| --- | --- | --- | --- |
| Run(작업) | 논리 요청 하나, client idempotency key(클라이언트 멱등성 키) 소유 | run ID(작업 식별자), canonical spec hash(정규 명세 해시), 요청자, execution/parse/check status(실행/파싱/검사 상태), 결과 attempt ID(실행 시도 식별자), provenance(출처 추적) 요약 | 동일 키와 동일 명세는 기존 Run(작업)을 반환한다. 다른 명세의 같은 키는 충돌이다. 종단 상태는 새 실행 시도 없이 되돌리지 않는다. |
| Attempt(실행 시도) | Run(작업)에 종속된 번호 있는 실행 하나, worker/lease(작업자/임대) 소유 | attempt number(실행 번호), 상태, worker ID(작업자 식별자), lease token(임대 토큰), heartbeat(심장박동), PID(프로세스 식별자), 시작·종료 시각, failure class(실패 등급), retry disposition(재시도 처리), raw artifact references(원시 산출물 참조) | 시작 전에 durable(지속) 행을 만든다. 하나의 attempt number(실행 번호)는 하나의 terminal outcome(종단 결과)만 갖는다. 새 재시도는 새 번호다. |

Run(작업) 상태는 `QUEUED → ACQUIRING → RUNNING → COLLECTING → PARSING → SUCCEEDED | FAILED | CANCELLED | TIMED_OUT`로 제한한다. Attempt(실행 시도)의 `ABANDONED`는 소유권 상실 또는 확인 불가를 나타내며, 성공과 동의어가 아니다. `parse status(파싱 상태)=INVALID`와 `check status(검사 상태)=FAIL`도 실행 상태와 합치지 않는다.

## 5. failure taxonomy(실패 분류)와 retry policy(재시도 정책)

| failure class(실패 등급) | 증거 | 기본 처리 | retry policy(재시도 정책) |
| --- | --- | --- | --- |
| configuration error(설정 오류) | 허용되지 않은 template(템플릿), 입력 hash(해시) 불일치, 필수 파일 부재 | 시작 전 거절 또는 실패 | 재시도 안 함 |
| resource unavailable(자원 사용 불가) | license/slot(라이선스/슬롯) 획득 실패 또는 admission timeout(입장 시간 초과) | 대기열 유지 또는 명시 실패 | 제한 횟수·jitter(지터) backoff(후퇴 지연), 예산 초과 시 실패 |
| spawn error(프로세스 시작 오류) | 실행 파일·work directory(작업 디렉터리)·권한 오류 | 실패 | 환경 변화가 없는 한 재시도 안 함 |
| tool exit(도구 종료 오류) | 관측된 nonzero exit code(0이 아닌 종료 코드) | 실패, 원시 결과 보존 | 재시도 안 함 |
| timeout(시간 초과) | 단계별 deadline(마감 시각) 도달 뒤 종료 절차 결과 | `TIMED_OUT` 또는 종료 불명 | 종료를 확인한 경우에만 제한 재시도 후보 |
| cancellation(취소) | 취소 요청과 실제 종료 확인 | `CANCELLED` | 재시도 안 함 |
| artifact missing(산출물 누락) | 종료 뒤 기대 report(보고서) 부재 | 실패 또는 불완전 | 일시적 저장소 오류 증거가 있을 때만 제한 재시도 |
| parse invalid(파싱 무효) | marker(완료 표식), 필수 필드, 단위, 유한 수치, 중복 검증 실패 | 실행은 별도 보존, 검사 `UNKNOWN` | 재시도 안 함 |
| check failed(검사 실패) | 유효한 보고서의 negative slack(음수 여유 시간) | 실행 성공, 검사 실패 | 재시도 안 함 |
| worker unavailable(작업자 사용 불가) | lease(임대) 만료와 owner heartbeat(소유자 심장박동) 부재, child process(하위 프로세스) 상태 미확정 | `ABANDONED` 또는 복구 필요 | 사람 정책 전까지 자동 재시도 안 함 |
| duplicate delivery(중복 전달) | 같은 event ID(이벤트 식별자) 또는 completion token(완료 토큰) 재도착 | no-op(무작업) 또는 기존 결과 반환 | 재시도 아님 |

재시도 횟수, backoff(후퇴 지연), timeout budget(시간 초과 예산)은 Run(작업) 명세에 기록하고 Attempt(실행 시도)마다 실제 값을 남긴다. `unknown execution outcome(알 수 없는 실행 결과)`는 성공도 재시도 가능도 아니다. 원인별 정책을 실제로 선택하기 전에는 `pending human decision(사람 결정 대기)`으로 남긴다.

### EDA(전자 설계 자동화) 세부 실패 분류

아래 분류는 위 공통 분류를 EDA(전자 설계 자동화) 입력·결과에 맞게 구체화하는 계획이다. 현재 구현이 모든 값을 발생·판정한다는 뜻이 아니다.

| 범주 | failure class(실패 등급) | 기본 처리 | 재시도 금지 또는 manual intervention(수동 개입) 사유 |
| --- | --- | --- | --- |
| Execution Failure(실행 실패) | `TIMEOUT`, `PROCESS_CRASH`, `WORKER_LOST`, `CANCELLED` | 종료 확인 전에는 결과 미확정, 확인 뒤 정책 적용 | `PROCESS_CRASH`와 `WORKER_LOST`는 외부 실행 완료 여부가 불명확하면 자동 재시도 금지; `CANCELLED`는 사용자 의도를 존중 |
| Input Failure(입력 실패) | `NETLIST_INVALID`, `LIBERTY_MISSING`, `SDC_INVALID`, `UNSUPPORTED_INPUT` | terminal failure(종단 실패) | 같은 입력을 반복해도 고쳐지지 않으므로 입력·지원 계약 수정 필요 |
| Tool Failure(도구 실패) | `TOOL_EXIT_NONZERO`, `TOOL_VERSION_UNSUPPORTED` | terminal failure(종단 실패), 원시 진단 보존 | 보고서 내부 값으로 종료 실패를 덮어쓸 수 없음; 환경·버전 변경은 사람 검토 필요 |
| Result Failure(결과 실패) | `REPORT_INCOMPLETE`, `PARSE_FAILED`, `SEMANTIC_INVALID` | 실행 상태와 분리하여 실패 또는 `UNKNOWN` 기록 | 반복 실행이 원문 누락·포맷·의미 오류를 해결하지 않음; parser(파서)·입력 계약 검토 필요 |
| Infrastructure Failure(인프라 실패) | `DB_TRANSIENT_ERROR`, `QUEUE_UNAVAILABLE`, `STORAGE_UNAVAILABLE` | durable write(지속 쓰기)·외부 실행 여부를 분리해 복구 판단 | 실행 전에 발생했거나, 실행 종료·산출물 보존을 독립적으로 확인할 때만 제한 재시도 후보 |

### Retry(재시도) 대안과 판별 기준

| 대안 | 장점 | 위험 | 채택 전 판별 지표 |
| --- | --- | --- | --- |
| no retry(재시도 없음) | 중복 외부 실행과 자원 낭비가 가장 작음 | 일시적 장애를 회복하지 못함 | 완료율, 수동 재제출 수 |
| fixed retry(고정 재시도) | 구현·설명이 단순함 | 장애 지속 시 같은 간격의 재시도 폭주 | retry storm(재시도 폭주), 총 완료 지연 |
| bounded retry(제한된 재시도) | 횟수·예산을 명시해 회복과 비용을 제한 | 적정 횟수는 workload(작업부하) 의존 | 일시적 장애 회복률, attempt count(실행 시도 수), 자원 점유 |
| exponential backoff(지수 백오프) | 지속 장애에서 재시도 압력을 낮춤 | 총 완료 지연과 정책 복잡성 증가 | total completion latency(전체 완료 지연), 대기열 연령, 실패율 |

Baseline(기준선)은 현재 no retry(재시도 없음) 또는 기존 제한 재시도 동작을 정확히 기록한 뒤 정한다. Challenger(도전 대안)는 하나만 선택한다. 동일한 장애 주입과 자원 한도에서 일시적 장애 회복률, 중복 실행 위험, CPU(중앙 처리 장치)·Memory(메모리)·license/slot(라이선스/슬롯) 낭비, total completion latency(전체 완료 지연), retry storm(재시도 폭주)을 비교하고 결과 전 adoption gate(채택 기준)를 기록한다.

## 6. timeout(시간 초과)·cancel(취소)·subprocess lifecycle(하위 프로세스 수명주기)

단계별 deadline(마감 시각)은 `acquire(획득)`, `execute(실행)`, `collect(수집)`, `parse(파싱)`에 분리한다. 호출자 HTTP timeout(HTTP 시간 초과)은 관측자 시간 제한일 뿐 실행 중단 증거가 아니다.

1. 취소 또는 execute timeout(실행 시간 초과)이 들어오면 Attempt(실행 시도)에 cancellation requested(취소 요청됨)와 시각을 먼저 기록한다.
2. worker(작업자)는 process group(프로세스 그룹)에 종료 신호를 보내고 grace period(유예 시간) 뒤 강제 종료를 시도한다. 시작하지 않은 작업은 즉시 취소할 수 있다.
3. stdout/stderr(표준 출력/표준 오류), signal(신호), exit code(종료 코드), 종료 확인 시각, 남은 artifact(산출물)를 수집한다.
4. child process(하위 프로세스)의 종료를 확인하지 못하면 `termination_unconfirmed(종료 미확인)`으로 남긴다. 이 상태를 `FAILED`, `CANCELLED`, 재시도 가능으로 단정하는 규칙은 사람 결정 전 도입하지 않는다.
5. release(반납)는 성공·실패·예외에서 모두 시도하되, 실패한 release(반납)도 별도 오류로 기록한다.

## 7. worker loss(작업자 손실)·heartbeat(심장박동)·lease(임대)·reconciliation(조정)

worker(작업자)는 lease owner(임대 소유자), fence token(차단 토큰), 만료 시각을 가진 lease(임대)를 획득한다. heartbeat(심장박동)는 작업자 생존 신호와 child process(하위 프로세스) 관측을 구분해 기록한다. stale timestamp(오래된 시각)만으로 외부 child process(하위 프로세스)가 죽었다고 결론 내리지 않는다.

reconciler(조정기)는 다음 순서로만 동작한다.

1. lease(임대)가 만료됐고 최근 heartbeat(심장박동)가 없는 Attempt(실행 시도)를 후보로 찾는다.
2. durable ownership(지속 소유권), fence token(차단 토큰), 기록된 process identity(프로세스 식별 정보), 가능한 종료 관측을 확인한다.
3. 이전 소유자의 완료 쓰기는 fence token(차단 토큰) 조건을 만족할 때만 허용한다.
4. 실행 결과가 불명확하면 Attempt(실행 시도)를 `ABANDONED`와 `recovery_required(복구 필요)`로 기록하고 Run(작업)을 성공시키지 않는다.
5. 재시도 또는 재제출은 명시 정책이 있을 때만 새 Attempt(실행 시도)를 만든다.

첫 실험은 single worker restart(단일 작업자 재시작)만 포함한다. 두 독립 worker(작업자)가 같은 외부 도구 자원을 동시에 소유하는 상황과 network partition(네트워크 분할)은 후속 증거 없이는 범위 밖이다.

대표 stale RUNNING(오래된 실행 중) 흐름은 `RUNNING → heartbeat(심장박동) 중단 → lease(임대) 만료 → WORKER_LOST(작업자 손실) 판정 → retryable(재시도 가능) 여부 판정 → 새 Attempt(실행 시도) 또는 terminal failure(종단 실패)`다. heartbeat interval(심장박동 간격)이 짧으면 탐지는 빨라지지만 DB write(데이터베이스 쓰기)와 관측 비용이 증가한다. 길면 비용은 줄지만 recovery time(복구 시간)이 늘어난다. 간격·lease duration(임대 기간)은 production SLA(운영 서비스 수준 협약)로 추정하지 않고, 장애 주입에서 탐지 지연·쓰기량·잘못된 회수 여부를 측정해 선택한다.

## 8. idempotency(멱등성)와 duplicate delivery(중복 전달)

- submit idempotency(제출 멱등성): `client key + canonical spec hash(정규 명세 해시)`가 하나의 Run(작업)을 식별한다. 같은 키에 다른 명세는 명시 충돌이다.
- attempt idempotency(실행 시도 멱등성): 새 Attempt(실행 시도)는 atomic compare-and-set(원자적 비교 후 설정)으로 하나의 다음 번호만 받는다.
- completion idempotency(완료 멱등성): `attempt ID + lease/fence token(임대/차단 토큰) + completion token(완료 토큰)`이 이미 처리되면 동일 결과를 반환하고 산출물·상태를 다시 쓰지 않는다.
- side-effect boundary(부수 효과 경계): OpenSTA(정적 타이밍 분석 도구) 작업 디렉터리는 attempt ID(실행 시도 식별자)별로 분리한다. 동일 attempt(실행 시도)의 재전송은 새 하위 프로세스를 만들지 않는다.

외부 도구 실행은 네트워크 손실 뒤 exactly-once(정확히 한 번)를 주장할 수 없다. 이 계획의 보장은 durable attempt history(지속 실행 이력), 중복 완료 무해성, 성공 승격 금지이며, 불명확한 외부 실행은 at-least-once risk(최소 한 번 위험)로 명시한다.

## 9. resource-aware concurrency(자원 인지 동시성)와 backpressure(역압)

동시성은 전역 worker count(작업자 수) 하나로 정하지 않는다. `tool version(도구 버전)`, `license class(라이선스 등급)`, `host capacity(호스트 용량)`, `work directory/storage quota(작업 디렉터리/저장소 할당량)`를 resource key(자원 키)로 모델링한다.

- admission control(입장 제어)은 실행 전 토큰, 예상 산출물 크기, 큐 대기 예산을 확인한다.
- scheduler(스케줄러)는 한 resource key(자원 키)의 한도를 넘지 않고, 장기 작업이 짧은 작업을 영구히 막지 않는지 관측한다.
- backpressure(역압)는 새 Run(작업)을 무한히 메모리에 쌓지 않고, 명시 대기·거절·클라이언트 재시도 시각을 반환하는 정책이다.
- 측정 전에는 실제 라이선스 수나 적정 worker count(작업자 수)를 가정하지 않는다. 초기 한도는 1이고, 증거가 있을 때만 하나씩 올린다.

동시 실행 수는 1/2/4/8처럼 bounded value(제한된 값)만 비교한다. 같은 OpenSTA(정적 타이밍 분석 도구) workload(작업부하)와 입력 혼합에서 queue wait(대기열 대기), execution latency(실행 지연), end-to-end latency(종단 간 지연), throughput(처리량), CPU(중앙 처리 장치), Memory(메모리), timeout rate(시간 초과율), failure rate(실패율), 실제 overlap(동시 실행 겹침)을 측정한다. saturation point(포화 지점)는 처리량 증가가 멈추거나 지연·시간 초과·실패가 허용한 실험 기준보다 악화되는 최초의 값으로 정의하며, 이것이 선택한 동시 실행 수의 근거가 된다.

FastAPI(파이썬 웹 프레임워크) async endpoint(비동기 종단점) 또는 다른 API(응용 프로그래밍 인터페이스) 비동기 처리는 요청 수락·DB(데이터베이스)·네트워크 대기에 유용할 수 있다. 그러나 OpenSTA(정적 타이밍 분석 도구)의 CPU(중앙 처리 장치)·subprocess(하위 프로세스) 실행을 자동으로 빠르게 만들지 않으며, 별도의 worker(작업자)·resource policy(자원 정책)·admission control(입장 제어)이 필요하다.

## 10. trace(추적)와 provenance(출처 추적)

각 Run(작업)과 Attempt(실행 시도)는 correlation ID(상관 식별자)로 API(응용 프로그래밍 인터페이스) 요청, 스케줄, lease(임대), 하위 프로세스, artifact(산출물), parser(파서), checker(검사기), reconciliation(조정) 기록을 연결한다.

최소 provenance(출처 추적) 묶음은 다음과 같다.

- source kind(출처 종류): `tool_generated(도구 생성)`, `fixture(고정 입력)`, `replay(재생)`;
- OpenSTA/Yosys(정적 타이밍 분석 도구/합성 도구) 버전·revision(리비전), command template ID(명령 템플릿 식별자), 입력·설정 hash(해시), 환경 식별 정보;
- raw stdout/stderr(원시 표준 출력/표준 오류), exit/signal(종료 코드/신호), report hash(보고서 해시), artifact path(산출물 경로), 보존 정책;
- execution/parse/check status(실행/파싱/검사 상태), completeness(완전성), failure class(실패 등급), retry decision(재시도 결정), 모든 상태 전이 시각과 actor(행위자).

민감한 license path(라이선스 경로), 환경 변수 값, 비밀값은 원문으로 보존하지 않는다. `tool_generated(도구 생성)` 결과와 fixture(고정 입력) 재생을 같은 실제 실행 증거로 표시하지 않는다.

Trace(추적)는 관측 장식이 아니라 병목·실패 원인·before/after(변경 전/후) 검증의 evidence(근거)다. 최소 경로는 `API(응용 프로그래밍 인터페이스) → queue wait(대기열 대기) → worker setup(작업자 설정) → Yosys(합성 도구, 선택적 fixture 생성) → OpenSTA(정적 타이밍 분석 도구) → parser(파서) → validator(검증기) → DB persist(데이터베이스 저장) → event publish(이벤트 발행, 채택된 경우)`로 잇는다. 각 span(구간)은 run ID(작업 식별자), attempt ID(실행 시도 식별자), duration(소요 시간), status(상태), error class(오류 등급), worker ID(작업자 식별자), tool version(도구 버전)을 연결한다. Redis Pub/Sub(레디스 발행/구독)은 이벤트 발행이 실제로 채택된 경우에만 이 경로에 넣으며, 기본 구성으로 가정하지 않는다.

## 11. alternatives(대안)와 trade-off(상충관계)

| 선택지 | 장점 | 비용·제약 | 현 단계 위치 |
| --- | --- | --- | --- |
| A. SQLite(라이트급 SQL 저장소) + 단일 worker(작업자) + durable attempt(지속 실행 시도) + lease(임대) | 가장 작은 실제 실행 경계를 검증할 수 있다 | 재시작·다중 호스트·강한 fencing(차단) 한계 | baseline(기준선) |
| B. PostgreSQL(포스트그레스큐엘) 기반 행 잠금·lease(임대) | 다중 프로세스 소유권과 조건부 전이에 더 강한 근거 | 운영 구성과 migration(마이그레이션) 비용 | adoption trigger(채택 조건) 뒤 challenger(도전 대안) |
| C. Redis(레디스) 기반 큐/락 | 빠른 대기열과 자원 토큰 실험 | 영속성·복구·락 유실 계약을 별도로 증명해야 한다 | 독립 비교가 필요할 때만 |
| D. Kafka(카프카) | 보존된 event log(이벤트 로그), replay(재생), 다중 consumer(소비자) | 운영·순서·재처리·중복 처리 복잡도 | 기본 도입 금지, 아래 확장 조건에서만 challenger(도전 대안) |

## 12. 개선 후보와 adoption trigger(채택 조건)

각 후보는 baseline(기준선) → 같은 workload(작업부하) → challenger(도전 대안) → 동일 workload revalidation(동일 작업부하 재검증) 한 번으로 판단한다.

| 개선 후보 | 관측 기반 adoption trigger(채택 조건) | 기각 조건 |
| --- | --- | --- |
| durable lease(지속 임대)와 fence token(차단 토큰) | 실제 worker restart(작업자 재시작)에서 오래된 소유자의 완료 쓰기 또는 불명확한 소유권이 재현됨 | 단일 소유자에서 현재 조건부 전이만으로 불변식 유지 |
| PostgreSQL(포스트그레스큐엘) | SQLite(라이트급 SQL 저장소) 잠금/복구 한계가 동일 workload(작업부하)에서 관측됨 | 가정된 운영 규모만으로는 채택하지 않음 |
| bounded queue(제한 대기열) | 메모리 대기열 증가, deadline breach(마감 위반), 자원 한도 초과가 측정됨 | 단순 worker count(작업자 수) 추측 |
| cancellation escalation(취소 단계 상승) | 종료 요청 뒤 child process(하위 프로세스) 잔존이 관측됨 | 호출자 timeout(시간 초과)만으로는 채택하지 않음 |
| Kafka(카프카) challenger(도전 대안) | 다음 모두가 실제 한계 실험에서 필요하다고 나타남: owner restart(소유자 재시작) 뒤 retained replay(보존 재생), 같은 lifecycle event(수명주기 이벤트)의 독립 다중 consumer(소비자), 독립 스케줄 재처리, run별 순서 보장, 현재 owner(소유자)를 넘는 backpressure/throughput(역압/처리량) 한계 | 이 중 하나라도 요구·측정되지 않았거나, 대안 비교가 없으면 기본 도입하지 않음 |

Kafka(카프카) 평가를 열 경우에도 retention window(보존 기간), consumer count(소비자 수), replay semantics(재생 의미), ordering key(순서 키), duplicate handling(중복 처리), 처리량·지연·장애 회복 결과를 같은 workload(작업부하)에서 비교한다.

## 13. 검증 계획: 5종 테스트와 TDD(테스트 주도 개발)

구현이 승인될 때 각 불변식은 TDD(테스트 주도 개발)의 Red(실패) → Green(통과) → Refactor(정리)로 진행한다. 탐색 코드나 benchmark harness(벤치마크 도구)는 먼저 탐색한 뒤 계약이 확정될 때 회귀 테스트로 고정한다.

| 종류 | 반드시 확인할 사례 |
| --- | --- |
| unit test(단위 테스트) | 상태 전이, failure classification(실패 분류), retry eligibility(재시도 적격성), idempotency key(멱등성 키), fence token(차단 토큰), 완료 중복 무해성 |
| integration test(통합 테스트) | SQLite(라이트급 SQL 저장소) 또는 선택 저장소 + 실제 OpenSTA(정적 타이밍 분석 도구) child process(하위 프로세스) + artifact collection(산출물 수집) + parser/checker(파서/검사기) + 재시작 경계 |
| regression test(회귀 테스트) | nonzero exit(0이 아닌 종료), exit=0/negative slack(음수 여유 시간), 누락 marker(완료 표식), timeout(시간 초과), 정상 취소, 중복 완료가 기존 구분을 무너뜨리지 않음 |
| fault-injection test(장애 주입 테스트) | artifact(산출물) 뒤 terminal write(종단 쓰기) 전 worker kill(작업자 종료), heartbeat stop(심장박동 중지), lease expiry(임대 만료), SIGTERM/SIGKILL(종료 신호), 수집 실패, 중복 delivery(전달) |
| contract test(계약 테스트) | EdaAdapter(EDA 어댑터)의 acquire/execute/collect/release(획득/실행/수집/반납), command template(명령 템플릿) 제한, provenance(출처 추적) 필수 필드, 실제/fixture(고정 입력) 표기 분리 |

각 중요 변경 뒤 Test Scope Review(테스트 범위 검토)를 한다. 단위 테스트 통과만으로 실제 프로세스 수명주기, 저장소 조건부 전이, 실제 보고서 provenance(출처 추적)를 증명하지 못하면 해당 불변식에 가장 작은 integration(통합)·fault-injection(장애 주입)·contract(계약) 검증을 더한다.

## 14. load(부하)·recovery(복구)·benchmark(벤치마크) 계획

### 측정 순서와 예산

1. baseline(기준선): concurrency=1(동시성 1), normal/tight SDC(정상/엄격 설계 제약) 각각 반복 실행으로 process duration(프로세스 시간), queue wait(대기열 대기), CPU/memory(중앙 처리 장치/메모리), artifact bytes(산출물 바이트), license/slot hold time(라이선스/슬롯 점유 시간), 상태 결과를 원시로 보존한다.
2. realistic workload(현실적 작업부하): 같은 입력 혼합과 정한 동시성 하나에서 실행한다. 요청 수, 성공·실패·취소·불명확 비율, admission rejection(입장 거절), p50/p95 latency(중앙/상위 95% 지연), queue age(대기열 경과), 실제 동시 실행 겹침을 기록한다.
3. recovery workload(복구 작업부하): 정해진 시점에서 worker restart(작업자 재시작), child timeout(하위 프로세스 시간 초과), completion duplicate(완료 중복)를 한 번씩 주입한다. Run(작업)·Attempt(실행 시도) 이력, 프로세스 종료 관측, lease(임대), artifact(산출물), 성공 승격 금지 여부를 대조한다.
4. smallest reinforcement(최소 보강): 한 불변식이 깨질 때만 하나의 보강 또는 challenger(도전 대안)를 고른다.
5. identical-workload revalidation(동일 작업부하 재검증): 같은 입력·반복 수·동시성·주입 시점으로 다시 측정하고 baseline(기준선)과 표로 비교한 뒤 멈춘다.

측정 결과는 실행 revision(리비전), 미커밋 변경 여부, 호스트·도구 버전, 명령, 원시 결과 경로, anomaly(이상)와 limitation(한계)을 `docs/evidence/`에 남긴다. 성능, 처리량, 복구율은 실제 결과가 나오기 전에는 계획 값으로만 기록한다.

## 15. CI/CD(지속적 통합/지속적 배포) gate(관문)와 운영·배포 검증

### CI(지속적 통합) gate(관문)

- unit/regression/contract test(단위/회귀/계약 테스트)는 모든 변경에서 통과해야 한다.
- 실제 OpenSTA(정적 타이밍 분석 도구)가 가능한 runner(실행기)에서는 고정 workload(작업부하)의 integration/fault-injection test(통합/장애 주입 테스트)를 별도 명시 job(작업)으로 실행한다. 도구가 없는 runner(실행기)는 허위 통과로 대체하지 않고 `not run(미실행)` 이유를 기록한다.
- schema migration(스키마 마이그레이션), 조건부 종단 전이, provenance(출처 추적) 필수 필드, normal/tight 결과 구분은 계약 위반 시 병합을 막는다.
- artifact(산출물) hash(해시)와 fixture/tool-generated(고정 입력/도구 생성) 출처 표기가 바뀌면 재검증을 요구한다.
- Docker build(도커 빌드), migration test(마이그레이션 테스트), PostgreSQL/Redis/worker integration(포스트그레스큐엘/레디스/작업자 통합)은 해당 구성 요소를 adoption gate(채택 기준) 뒤 실제로 선택한 경우에만 CI(지속적 통합) 관문에 추가한다. 선택하지 않은 구성의 미실행을 통과로 위장하지 않는다.

### 운영·배포 검증

배포 전에는 단일 canary(카나리) Run(작업)으로 정상·타이밍 위반·시간 초과/취소 중 승인된 사례를 실행하고, 로그만이 아니라 durable state(지속 상태), lease release(임대 반납), artifact linkage(산출물 연결), retry/reconciliation(재시도/조정) 이력을 확인한다. staging(스테이징) 또는 배포 환경에서 worker restart/recovery smoke(작업자 재시작/복구 간이 검증)는 실제 worker(작업자) 실행을 선택했을 때만 수행한다. rollback(되돌리기) 기준은 정상 실행이 성공으로 보존되지 않음, 실패가 성공으로 승격됨, lease(임대)·자원 누수, provenance(출처 추적) 누락이다. 실제 배포는 별도 승인 없이는 수행하지 않는다.

## 16. Falsification(반증)과 Stop condition(종료 조건)

### Falsification condition(반증 조건)

- baseline(기준선)이 실제 하위 프로세스 종료·자원 반납·상태 전이를 이미 안전하게 보존하면 해당 보강을 도입하지 않는다.
- timeout(시간 초과) 또는 worker restart(작업자 재시작) 뒤에도 child process(하위 프로세스)가 살아 있는데 reconciler(조정기)가 Run(작업)을 종단 실패·성공으로 변경하면 그 복구 규칙을 기각한다.
- duplicate delivery(중복 전달)가 새 Attempt(실행 시도), 새 외부 실행, 또는 다른 terminal result(종단 결과)를 만들면 멱등성 설계를 기각한다.
- resource limit(자원 한도)를 넘긴 실제 겹침 증거가 없으면 concurrency(동시성) 확대나 큐·브로커 채택 주장을 기각한다.
- Kafka(카프카) 필요 조건이 실제 한계 실험에서 모두 충족되지 않으면 Kafka(카프카) challenger(도전 대안)를 열지 않는다.

### Stop condition(종료 조건)

다음 한 사이클이 닫히면 멈춘다.

1. 하나의 실제 OpenSTA(정적 타이밍 분석 도구) subprocess lifecycle failure(하위 프로세스 수명주기 실패)를 재현한다.
2. baseline(기준선)과 최대 하나의 최소 reinforcement(보강) 또는 challenger(도전 대안)를 같은 workload(작업부하)에서 비교한다.
3. Run/Attempt(작업/실행 시도), 상태 분리, 자원 한도, 중복 무해성, 성공 승격 금지 불변식을 5종 테스트에 필요한 범위로 검증한다.
4. load/recovery benchmark(부하/복구 벤치마크)를 동일 workload(작업부하)에서 재검증하고 원시 근거·한계·미측정 범위를 기록한다.
5. Human Decision Gate(사람 결정 관문)에 실제 결과와 trade-off(상충관계)를 제시한다.

완료 뒤에는 자동으로 새 failure mode(실패 모드), Redis(레디스), PostgreSQL(포스트그레스큐엘), Kafka(카프카), 다중 도구 또는 확장 배포로 넘어가지 않는다. 다음 문제는 별도 사람 결정과 새 계획을 필요로 한다.

## 17. 기록 위치

이 프로젝트 저장소가 코드·계획·결정·증거의 source of truth(원본 기준)다.

- 이 계획은 `docs/plans/`에 둔다.
- 실행 결과, 원시 산출물 참조, 측정 한계는 `docs/evidence/`에 둔다.
- 실제 선택, Human Decision Gate(사람 결정 관문), Changed belief(변경된 판단)는 `docs/decisions/`에 둔다.
- Career OS(커리어 운영체제)에는 이 저장소의 revision(리비전)과 위 원본 문서 링크, 제한을 포함한 짧은 요약과 역량 연결만 남긴다. 원시 로그·결정·증거 전문을 중복 저장하거나 Career OS를 원본으로 사용하지 않는다.
