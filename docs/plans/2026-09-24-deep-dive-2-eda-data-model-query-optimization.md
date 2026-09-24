# 두 번째 EDA(전자 설계 자동화) 딥다이브 계획서: EDA Result Modeling & Workload-driven Query Optimization(EDA 결과 모델링 및 업무 조회 기반 쿼리 최적화)

작성일: 2026-09-24
선행 근거: [범위·깊이·종료 검토](2026-09-24-scope-depth-closure-review.md), [첫 번째 실행 신뢰성 딥다이브](2026-09-24-eda-execution-correctness-deep-dive.md), [대형 parser/DB(파서/데이터베이스) synthetic benchmark(합성 벤치마크)](../evidence/parser-db-benchmark.md), [실제 OpenSTA(정적 타이밍 분석 도구) 증거](../evidence/2026-09-24-real-sta/README.md), [출처 장부](../references/source-register-2026-09-23.md)

## 1. 문제·범위·업무 근거

### 대표 문제

EDA(전자 설계 자동화) 분석 이력이 반복적으로 쌓일 때, 회로·EDA 엔지니어가 이번 revision(설계 버전)에서 무엇이 악화됐는지, 새로운 violation(위반)이 무엇인지, 특정 endpoint/path(종점/경로)가 revision(설계 버전)별로 어떻게 변했는지를 빠르고 신뢰성 있게 조회하도록 결과를 모델링하고 query(조회)를 최적화한다.

공개 업무 근거 J0/J2/J3는 RDB(관계형 데이터베이스) 설계, data modeling(데이터 모델링), query optimization(쿼리 최적화), 반도체 로그·리포트 파싱, migration(마이그레이션), CI/CD(지속적 통합/지속적 배포)를 함께 언급한다. 이것은 EDA-shaped data workload(EDA 형태의 데이터 작업부하)를 선택하는 근거다. 회사 내부 DB(데이터베이스) 구조, row count(행 수), query(조회), 운영 SLA(서비스 수준 협약)는 공개되지 않았으므로, 이 계획의 모든 데이터 크기·분포·성능 기준은 synthetic bounded workload(범위 제한 합성 작업부하)다.

### 첫 번째 딥다이브와의 경계

| 책임 | 첫 번째 EDA Execution Reliability Deep Dive(EDA 실행 신뢰성 딥다이브) | 두 번째 EDA Result Modeling & Workload-driven Query Optimization(EDA 결과 모델링 및 업무 조회 기반 쿼리 최적화) |
| --- | --- | --- |
| 대표 질문 | 외부 tool process(도구 프로세스)의 실행·복구·자원 한도를 어떻게 신뢰성 있게 보존하는가 | 보존된 결과를 어떤 조건에서 비교하고, 대표 조회를 어떻게 측정해 개선하는가 |
| 소유 모델 | Run(작업), Attempt(실행 시도), lease(임대), retry(재시도), reconciliation(상태 재조정) | Design(설계), Revision(설계 버전), Artifact(산출물), Metric(요약 지표), Finding(발견 항목), comparability(비교 가능성) |
| 공통 요소 | provenance(출처 추적)는 실행 사실·도구·입력·상태 전이를 증명 | provenance(출처 추적)는 비교 가능 조건과 query filter(조회 필터)를 결정 |
| 범위 밖 | 저장 구조의 대규모 읽기 최적화 | worker(작업자), queue(대기열), subprocess lifecycle(하위 프로세스 수명주기) 변경 |

첫 번째 계획의 Run(작업)과 Attempt(실행 시도)는 이 계획에서도 참조하지만 재설계하지 않는다. 이 계획은 parser(파서)·worker(작업자)·API(응용 프로그래밍 인터페이스) 구현을 시작하지 않으며, 첫 계획의 실행 증거를 데이터 성능 증거로 바꾸지 않는다.

## 2. Human Gate(사람 결정 관문)

- Human Problem(사람 문제): 사용자가 우선시할 대표 query workload(조회 작업부하)는 unrecorded(기록되지 않음).
- Human hypothesis(사람 가설): unrecorded(기록되지 않음).
- Prediction(예측): unrecorded(기록되지 않음).
- AI/challenger hypothesis(AI/도전 가설): 동일한 correctness invariant(정확성 불변식)를 유지하는 범위에서, 대표 query(조회)를 유도하는 복합 인덱스가 해당 query(조회) 지연을 줄일 수 있다. 실제 효과·비용은 측정 전 미확정이다.
- Decision required(필요한 결정): 대표 query(조회) 우선순위, synthetic workload(합성 작업부하) 경계, adoption gate(채택 기준), index/materialization(인덱스/사전 계산) 채택 여부를 사용자가 결정한다.
- Changed belief(변경된 판단): pending human decision(사람 결정 대기).
- Stop condition/Budget(종료 조건/예산): 하나의 모델·식별 전략과 최대 하나의 query optimization(쿼리 최적화) challenger(도전 대안)를 같은 workload(작업부하)에서 before/after(변경 전/후)로 검증한 뒤 멈춘다. partitioning(파티셔닝), 새 broker(브로커), production migration(운영 마이그레이션)은 자동으로 열지 않는다.

## 3. 데이터 모델과 불변식

```text
Design(설계)
  → Revision(설계 버전)
    → Run(분석 작업)
       ├─ Attempt(실행 시도)
       ├─ Artifact(산출물)
       ├─ Metric(요약 지표)
       └─ Finding(발견 항목)
```

| 모델 | 의미 | 최소 필드 | 불변식 |
| --- | --- | --- | --- |
| Design(설계) | 비교 대상 논리 설계 | design ID(설계 식별자), 이름 | 다른 설계를 같은 revision(설계 버전) 계열로 섞지 않음 |
| Revision(설계 버전) | 설계 변경의 식별 가능한 기준 | revision ID(버전 식별자), source revision(소스 리비전), 생성 시각 | source revision(소스 리비전) 미상은 비교 근거로 승격하지 않음 |
| Run(분석 작업) | 하나의 분석 요청의 종단 결과 | run ID(작업 식별자), execution/parse/check status(실행/파싱/검사 상태), input provenance(입력 출처 추적) | execution(실행), parse(파싱), check(검사)를 하나의 성공값으로 합치지 않음 |
| Attempt(실행 시도) | Run(작업)의 개별 실행 이력 | attempt number(실행 번호), worker ID(작업자 식별자), exit code(종료 코드), failure class(실패 등급), trace ID(추적 식별자), resource usage(자원 사용량) | 덮어쓰기 대신 번호가 있는 이력을 보존 |
| Artifact(산출물) | 원문 report/log(보고서/로그)와 재현 입력 | URI(통합 자원 식별자) 또는 경로, hash(해시), source kind(출처 종류), 보존 정책 | raw artifact(원시 산출물)와 정규화 결과를 연결 |
| Metric(요약 지표) | Run(작업) 수준의 비교 가능한 집계 | WNS(최악 음의 여유), TNS(총 음의 여유), violation count(위반 수), 단위, scope(범위) | 분석 범위·단위 없는 수치를 비교하지 않음 |
| Finding(발견 항목) | 개별 timing path(타이밍 경로) 또는 위반 | startpoint(시작점), endpoint(종점), path group(경로 그룹), analysis type(분석 유형), corner(코너), slack ns(여유 시간 나노초) | Finding(발견 항목)의 identity(식별)·비교 조건을 별도 보존 |

현재 실제 OpenSTA(정적 타이밍 분석 도구) 증거는 단일 setup/max(최대 지연) path(경로)와 고정 profile(프로파일)만 다룬다. WNS(최악 음의 여유), TNS(총 음의 여유), 여러 Finding(발견 항목)은 두 번째 딥다이브에서 사용할 synthetic EDA-shaped data(EDA 형태의 합성 데이터) 모델이며, 현재 실제 도구에서 이미 얻었다고 주장하지 않는다.

## 4. Finding identity(발견 항목 식별)와 comparability(비교 가능성)

### Finding identity(발견 항목 식별) 후보

| 후보 | 장점 | collision/false match risk(충돌/잘못된 일치 위험) | 판별 질문 |
| --- | --- | --- | --- |
| `startpoint + endpoint` | 단순하고 조회 키가 짧음 | 다른 path group(경로 그룹), analysis type(분석 유형), corner(코너)를 같은 발견으로 합칠 수 있음 | 같은 두 핀이 다른 분석에서 같은 의미인가 |
| `startpoint + endpoint + path group` | 클록·경로 문맥을 보존 | analysis type(분석 유형)·corner(코너) 충돌 가능 | 그룹만으로 비교 범위를 충분히 고정하는가 |
| `startpoint + endpoint + path group + analysis type + corner` | 현재 지원 범위에서 가장 명시적 | 키·인덱스 크기와 저장 비용 증가 | 같은 물리·분석 조건의 반복 결과를 안정적으로 연결하는가 |

Baseline(기준선)은 가장 약한 식별 후보가 실제 synthetic workload(합성 작업부하)에서 만드는 false match(잘못된 일치)를 보인다. Challenger(도전 대안)는 하나의 더 강한 후보만 비교한다. 동일 경로가 아닌 Finding(발견 항목)을 새 violation(위반)으로 잘못 표시하거나, 동일 Finding(발견 항목)을 누락하는 경우는 성능 이득과 무관하게 기각한다.

### Comparability(비교 가능성) 규칙

Revision(설계 버전) A와 B의 WNS(최악 음의 여유)·TNS(총 음의 여유)·Finding(발견 항목)을 조건 없이 비교하지 않는다. 다음 provenance(출처 추적) 차이를 비교 전 검사한다: Liberty hash(라이브러리 해시), SDC hash(설계 제약 해시), tool version(도구 버전), parser version(파서 버전), corner(코너), analysis type(분석 유형).

| 상태 | 의미 | query(조회) 처리 |
| --- | --- | --- |
| `COMPARABLE` | 모든 필수 비교 조건이 같은 범위에서 확인됨 | 변화량·새 Finding(발견 항목)을 계산 가능 |
| `CONDITION_CHANGED` | Liberty(라이브러리), SDC(설계 제약), corner(코너), analysis type(분석 유형) 차이 | 나란히 표시하되 변화량을 동일 조건 regression(회귀)로 표기하지 않음 |
| `TOOL_CHANGED` | tool/parser version(도구/파서 버전) 차이 | 도구 변화 표시와 재검증 필요 |
| `INCOMPARABLE` | 필수 provenance(출처 추적)가 없거나 범위가 불명확 | 비교 결과를 반환하지 않거나 명시적 사유와 함께 보류 |

비교 편의성을 위해 `INCOMPARABLE`을 0·동일·개선으로 바꾸지 않는다.

## 5. Storage Strategy(저장 전략) 대안

| 대안 | 내용 | 장점 | 비용·위험 |
| --- | --- | --- | --- |
| A. Full detail(전체 상세) | 모든 timing path(타이밍 경로) 저장 | 임의 분석과 재해석 여지 | storage(저장소), ingestion time(적재 시간), index size(인덱스 크기), 쓰기 비용 증가 |
| B. Violations only(위반만) | 위반 Finding(발견 항목)만 저장 | 저장·조회 비용 감소 | 정상→위반 변화의 근거와 일부 분석 맥락이 부족할 수 있음 |
| C. Summary + violations + selected critical path + raw artifact(요약+위반+선택된 핵심 경로+원시 산출물) | Metric(요약 지표), 위반, 정한 critical path(핵심 경로), 원문 연결 보존 | 실무형 비교·원문 재검증의 균형 | 선택 기준·원문 보존·조회 조합이 복잡해질 수 있음 |

정답을 미리 정하지 않는다. 각 대안을 같은 synthetic EDA-shaped workload(EDA 형태의 합성 작업부하)에서 분석 가능성, storage(저장소), ingestion time(적재 시간), index size(인덱스 크기), query latency(조회 지연), 운영 복잡성으로 비교한다. Raw artifact(원시 산출물)를 잃어버린 정규화 결과는 parser(파서) 오류나 비교 판단을 역추적할 수 없으므로 채택하지 않는다.

## 6. 대표 Query Workload(조회 작업부하)

| ID | query(조회) | 모델·인덱스 요구 |
| --- | --- | --- |
| Q1 | 최근 N개 Revision(설계 버전)의 WNS/TNS/violation count(최악 음의 여유/총 음의 여유/위반 수) 추이 | Design(설계)·Revision(설계 버전) 순서, 비교 가능 조건, Metric(요약 지표) 범위 |
| Q2 | 이전 Run(작업) 대비 새 violation(위반) | Finding identity(발견 항목 식별), comparability(비교 가능성), anti-join(반대 조인) 비용 |
| Q3 | 한 Run(작업)의 worst N timing path(최악 N개 타이밍 경로) | Run(작업)·analysis type(분석 유형)·corner(코너) 필터와 slack ns(여유 시간 나노초) 정렬 |
| Q4 | 특정 endpoint(종점)의 Revision(설계 버전)별 slack history(여유 시간 이력) | endpoint(종점)·Finding identity(발견 항목 식별)·Revision(설계 버전) 순서 |
| Q5 | FAILED Run(실패 작업)의 최근 Attempt(실행 시도)와 failure class(실패 등급) | Run(작업) 상태·Attempt(실행 시도) 번호·최신 시각 |

Q1~Q5는 모두 구현 요구가 아니라 query contract(조회 계약) 후보다. Human Gate(사람 결정 관문)에서 우선순위 하나를 고르고, 나머지는 correctness regression(정확성 회귀)과 index side-effect(인덱스 부작용) 확인용으로만 사용한다.

## 7. Query Optimization(쿼리 최적화) 계획

선택한 RDBMS(관계형 데이터베이스 관리 시스템)가 PostgreSQL(포스트그레스큐엘)일 때만 `EXPLAIN (ANALYZE, BUFFERS)`를 사용한다. SQLite(라이트급 SQL 저장소) 기준선은 같은 실행 계획 정보를 제공하지 않으므로, PostgreSQL(포스트그레스큐엘) 결과와 같은 종류의 수치로 가장하지 않는다.

각 query(조회)의 before/after(변경 전/후)에서 다음을 보존한다.

- execution time(실행 시간), rows scanned(스캔 행 수), buffer hit/read(버퍼 적중/읽기), sort cost(정렬 비용), index scan(인덱스 스캔) 여부;
- index size(인덱스 크기), insert/update cost(삽입/갱신 비용), seed/ingestion time(시드/적재 시간), 결과 행·정렬·페이지 경계의 correctness(정확성);
- DBMS(관계형 데이터베이스 관리 시스템) 버전, schema revision(스키마 리비전), workload seed(작업부하 시드), query parameter(조회 매개변수), raw plan(원시 계획) 경로.

후보는 composite index(복합 인덱스), partial index(부분 인덱스), covering index(커버링 인덱스), keyset pagination(키셋 페이지네이션), materialization(사전 계산), partitioning(파티셔닝)이다. 후보는 한 번에 하나만 challenger(도전 대안)로 비교한다. partitioning(파티셔닝)은 현재 workload(작업부하)에서 table/index size(테이블/인덱스 크기), maintenance(유지보수), query plan(쿼리 실행 계획) 한계가 관측되기 전 도입하지 않는다.

## 8. Trade-off(상충관계)와 Adoption Gate(채택 기준)

| trade-off(상충관계) | 측정으로 답할 질문 |
| --- | --- |
| Full detail(전체 상세) vs storage/query complexity(저장/조회 복잡성) | 상세 행이 Q1~Q5의 분석 가치를 높이는 만큼 저장·색인 비용을 정당화하는가 |
| Read performance(조회 성능) vs write cost(쓰기 비용) | index(인덱스)가 선택 query(조회)를 줄이는 대신 ingestion(적재)을 과도하게 늦추는가 |
| Normalize-on-read(조회 시 계산) vs precompute/materialize(사전 계산) | 계산 비용을 줄이는 대신 stale result(오래된 결과)·갱신 계약을 늘리는가 |
| Comparison convenience(비교 편의성) vs correctness(정확성) | 비교 조건을 생략한 빠른 query(조회)가 잘못된 regression(회귀)을 만들지 않는가 |
| Index benefit(인덱스 이득) vs maintenance cost(유지 비용) | index size(인덱스 크기)와 write amplification(쓰기 증폭)을 감수할 실측 이득이 있는가 |

Adoption Gate(채택 기준)는 결과 전에 기록한다. 예시는 선택 query(조회)의 p95 query latency(상위 95% 조회 지연)가 baseline(기준선)보다 의미 있게 감소하고, 결과 행·정렬·comparability(비교 가능성) 불변식이 같으며, ingestion overhead(적재 오버헤드)와 index maintenance cost(인덱스 유지 비용)가 사용자가 정한 실험 예산 안에 남는 경우다. 이 기준은 production SLA(운영 서비스 수준 협약)가 아니라 실험 판단 기준이다.

## 9. Synthetic EDA-shaped Benchmark(EDA 형태의 합성 벤치마크)

workload(작업부하)는 `N designs(설계 수) × N revisions/design(설계당 버전 수) × N runs/revision(버전당 작업 수) × N findings/run(작업당 발견 수)`로 매개변수화한다. 구체적 N은 실험 전 Human Gate(사람 결정 관문)에서 작은 기준선과 현실적 비교 두 단계로 정한다. 고정 seed(시드), 생성기 revision(생성기 리비전), 분포 설명, 생성 원시 결과를 보존한다.

uniform random(균등 무작위)만 사용하지 않는다. 다음 EDA-like distribution(EDA 유사 분포)을 포함한다.

- 대부분은 정상 path(경로)이고 일부만 violation(위반)이다.
- 일부 endpoint(종점)는 반복되어 Q4(조회 4)의 이력 조회가 의미 있다.
- 특정 Revision(설계 버전)에서 controlled regression(통제된 회귀)을 넣어 Q2(조회 2)의 새 위반 판별을 검증한다.
- 동일 endpoint(종점)라도 corner(코너)·analysis type(분석 유형) 차이를 넣어 Finding identity(발견 항목 식별) 충돌을 검증한다.
- 일부 Run(작업)은 FAILED(실패)·불완전 provenance(출처 추적)로 만들어 Q5(조회 5)와 comparability(비교 가능성) 보류를 검증한다.

## 10. Schema Evolution & Migration(스키마 진화 및 마이그레이션)

parser v1(파서 버전 1)에서 parser v2(파서 버전 2)로 corner(코너)·analysis type(분석 유형) 필드가 추가되는 경우를 대표 시나리오로 둔다. 이는 단순 DDL(데이터 정의 언어) 변경이 아니라 historical data meaning(과거 데이터 의미)과 비교 규칙을 보존하는 문제다.

| 단계 | 검증 내용 |
| --- | --- |
| backward-compatible migration(하위 호환 마이그레이션) | old worker/new API(이전 작업자/새 API)가 같은 기간에 필요한 읽기·쓰기를 수행하는 계약 |
| backfill(과거 데이터 채우기) | 추론으로 채운 값과 원문에서 확인한 값을 구분하고, 원본 없는 행을 `INCOMPARABLE`로 남김 |
| rollback(되돌리기) | 새 열·인덱스·계산 결과를 되돌려도 원시 Artifact(산출물)와 기존 query meaning(조회 의미)을 훼손하지 않음 |
| interrupted migration(중단된 마이그레이션) | partial backfill(부분 과거 데이터 채우기), stale schema(오래된 스키마), 재실행의 멱등성 |

실제 운영 데이터 migration(마이그레이션)이나 데이터 삭제는 이 계획 범위가 아니다.

## 11. Testing Discipline(테스트 습관)과 증거

구현이 승인된 뒤에는 탐색 → problem/invariant(문제/불변식) 확정 → Red-Green-Refactor(실패-통과-정리) → Test Scope Review(테스트 범위 검토) → 필요한 integration/contract/fault-injection(통합/계약/장애 주입) 확장 순서로 진행한다. 모든 구현에 TDD(Test-Driven Development, 테스트 주도 개발)를 기계적으로 강제하지 않으며, query contract(조회 계약), identity(식별), comparability(비교 가능성), 발견된 결함에 우선 적용한다.

| 종류 | 최소 사례 |
| --- | --- |
| Unit Test(단위 테스트) | Finding identity(발견 항목 식별), Metric(요약 지표) 단위·범위, comparability(비교 가능성), pagination token(페이지네이션 토큰) |
| Integration Test(통합 테스트) | 선택 RDBMS(관계형 데이터베이스 관리 시스템)에서 Q1~Q5, migration(마이그레이션) 호환성, 실제 query plan(쿼리 실행 계획) 수집 |
| Regression Test(회귀 테스트) | index/schema(인덱스/스키마) 변경 뒤 같은 seed(시드)의 결과 의미·정렬·필터 유지 |
| Contract Test(계약 테스트) | pagination/sort/filter API(페이지네이션/정렬/필터 API), `INCOMPARABLE` 표현, 원시 artifact(산출물) 연결 |
| Fault Injection Test(장애 주입 테스트) | migration interruption(마이그레이션 중단), partial backfill(부분 과거 데이터 채우기), stale schema(오래된 스키마), index creation failure(인덱스 생성 실패) |

Benchmark(벤치마크)는 performance evidence(성능 근거)로 별도 보존하며, 테스트 통과로 성능 개선을 주장하지 않는다. Test Scope Review(테스트 범위 검토)는 “분포가 너무 단순한가”, “한 query(조회)만 과도하게 최적화했는가”, “읽기는 빨라졌지만 적재가 과도하게 느려졌는가”, “빠른 비교가 provenance(출처 추적) 조건을 생략했는가”를 확인한다.

## 12. CI/CD(지속적 통합/지속적 배포)와 역할 분담

CI(지속적 통합)는 unit/regression/contract test(단위/회귀/계약 테스트), schema migration test(스키마 마이그레이션 테스트), seed determinism(시드 결정성), 대표 query result(조회 결과) 회귀를 확인한다. PostgreSQL(포스트그레스큐엘) 기반 `EXPLAIN (ANALYZE, BUFFERS)` benchmark(벤치마크)는 해당 DBMS(관계형 데이터베이스 관리 시스템)를 실제로 선택한 runner(실행기)에서만 수행하고, 도구 부재를 성공으로 바꾸지 않는다. Docker build(도커 빌드)와 staging(스테이징) 검증은 컨테이너·배포가 실제 채택된 이후에만 범위에 넣는다.

Agent(에이전트)는 synthetic fixture(합성 고정 입력) 생성, 대량 seed(시드) 준비, `EXPLAIN (ANALYZE, BUFFERS)` 반복, index candidate(인덱스 후보) 초안, benchmark aggregation(벤치마크 집계), 결과 표 작성을 맡을 수 있다. Human(사람)은 대표 query workload(조회 작업부하), 우선순위, adoption gate(채택 기준), index/materialization(인덱스/사전 계산) 최종 선택, trade-off(상충관계), 종료 결정을 소유한다.

## 13. Falsification(반증)과 Stop Condition(종료 조건)

- Finding identity(발견 항목 식별)를 강화해도 false match(잘못된 일치)가 줄지 않거나 같은 Finding(발견 항목)을 누락하면 해당 전략을 기각한다.
- index(인덱스)가 query latency(조회 지연)를 낮춰도 결과 의미·정렬·comparability(비교 가능성)를 바꾸거나 쓰기 비용이 사전 예산을 넘으면 채택하지 않는다.
- materialization(사전 계산)이 stale result(오래된 결과)를 안전하게 무효화하지 못하면 채택하지 않는다.
- partitioning(파티셔닝)을 제외한 단순 대안이 같은 workload(작업부하)에서 충분하면 partitioning(파티셔닝)을 도입하지 않는다.

다음이 충족되면 멈춘다.

1. 도메인 기반 데이터 모델, Finding identity(발견 항목 식별), comparability(비교 가능성)를 15분 동안 근거와 한계까지 설명할 수 있다.
2. Q1~Q5 중 사람이 선택한 핵심 query(조회)의 `EXPLAIN (ANALYZE, BUFFERS)` before/after(변경 전/후) 원시 계획과 결과 표가 있다.
3. read/write/storage trade-off(읽기/쓰기/저장 상충관계)와 schema migration scenario(스키마 마이그레이션 시나리오)를 같은 workload(작업부하)에서 검증했다.
4. 사용하지 않은 기술, 특히 partitioning(파티셔닝)을 왜 채택하지 않았는지 실제 비교 결과로 설명할 수 있다.
5. Human Decision Gate(사람 결정 관문)에 결과·한계·다음 선택지를 제시했다.

완료 뒤에는 자동으로 첫 번째 딥다이브의 실행 복구, 추가 index(인덱스), materialization(사전 계산), partitioning(파티셔닝), broker(브로커), 배포로 넘어가지 않는다.

## 14. 기록 위치

프로젝트 저장소가 계획·구현·실험·결정의 source of truth(원본 기준)다. 이 계획은 `docs/plans/`에, 실제 query plan(쿼리 실행 계획)·benchmark(벤치마크) 원시 결과와 제한은 `docs/evidence/`에, 채택 또는 보류 판단은 `docs/decisions/`에 기록한다. Career OS(커리어 운영체제)는 저장소 revision(리비전), 원본 문서 링크, 짧은 결과·한계 요약, 역량 연결만 보존하며 원시 근거·결정 전문을 중복하지 않는다.
