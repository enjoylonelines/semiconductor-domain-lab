# 세 번째 EDA(전자 설계 자동화) 딥다이브 계획서: EDA Result Correctness & Contract Validation(EDA 결과 정합성 및 계약 검증)

작성일: 2026-09-24
선행 근거: [범위·깊이·종료 검토](2026-09-24-scope-depth-closure-review.md), [첫 번째 실행 신뢰성 딥다이브](2026-09-24-eda-execution-correctness-deep-dive.md), [두 번째 결과 모델링 딥다이브](2026-09-24-deep-dive-2-eda-data-model-query-optimization.md), [실제 OpenSTA(정적 타이밍 분석 도구) 증거](../evidence/2026-09-24-real-sta/README.md), [OpenSTA(정적 타이밍 분석 도구) 구현 결과](../evidence/2026-09-24-real-sta/implementation-result.md), [출처 장부](../references/source-register-2026-09-23.md)

## 1. 대표 문제와 Human Gate(사람 결정 관문)

EDA tool(EDA 도구)이 report(리포트)와 timing value(타이밍 값)를 출력했다고 해서 곧바로 신뢰 가능한 분석 결과로 사용해서는 안 된다. 실행 성공 여부, report structure(리포트 구조) 완전성, 분석 의미, 입력 조건, tool/parser version(도구/파서 버전), raw artifact provenance(원시 산출물 출처 추적)를 검증하여 잘못되거나 불완전한 EDA result(EDA 결과)가 정상 결과로 승격되는 것을 막는다.

핵심 흐름은 `Raw EDA Output(원시 EDA 출력) → Validation(검증) → Trust Decision(신뢰 판정) → Normalized Result(정규화 결과)`다.

- Observed problem(관측된 문제): 현재 실제 OpenSTA(정적 타이밍 분석 도구) slice(슬라이스)는 한 개 setup/max(최대 지연) profile(프로파일)에서 execution/parse/check(실행/파싱/검사) 분리와 일부 invalid(무효) 입력 거부를 보인다. hold/min(최소 지연), 복수 scope(범위), semantic mismatch(의미 불일치), 도구 버전 변화의 결과 신뢰 계약은 검증하지 않았다.
- Human hypothesis(사람 가설): unrecorded(기록되지 않음).
- Prediction(예측): unrecorded(기록되지 않음).
- AI/challenger hypothesis(AI/도전 가설): execution/structural/semantic/provenance(실행/구조/의미/출처)를 분리하고 fail-closed(의심 시 차단) trust rule(신뢰 규칙)을 적용하면 현재 실제 fixture(고정 입력)와 변형 fixture(고정 입력)에서 false trusted result(거짓 신뢰 결과)를 없앨 수 있다. 부분 데이터의 운영 유용성은 별도 검증이 필요하다.
- Decision required(필요한 결정): trusted result(신뢰 결과)의 최소 조건, partial data(부분 데이터) 노출 범위, parser strategy(파서 전략), trust model(신뢰 모델)과 adoption gate(채택 기준)를 사용자가 결정한다.
- Changed belief(변경된 판단): pending human decision(사람 결정 대기).
- Stop condition/Budget(종료 조건/예산): 실제 OpenSTA(정적 타이밍 분석 도구) fixture(고정 입력)와 최대 하나의 parser/trust challenger(파서/신뢰 도전 대안)를 같은 mutation/corruption workload(변형/손상 작업부하)에서 비교한 뒤 멈춘다. 새 EDA vendor(EDA 벤더), P&R(배치·배선), worker(작업자), DB schema(데이터베이스 스키마), queue(대기열) 구현은 열지 않는다.

## 2. 도메인·업무 환경 근거

회로 엔지니어는 Synthesis(합성), STA(정적 타이밍 분석), CDC(클록 도메인 교차), Lint(정적 검사), Formal Verification(정형 검증) 등 서로 다른 EDA result(EDA 결과)를 반복 검토한다. timing result(타이밍 결과)는 단순 숫자가 아니라 setup/hold(설정/유지), max/min path(최대/최소 경로), corner(코너), path group(경로 그룹), SDC(설계 제약), Liberty(셀 라이브러리), report scope(리포트 범위)와 함께 해석돼야 한다.

tool execution(도구 실행)이 실패했는데 일부 report(리포트)가 남을 수 있고, report parsing(리포트 파싱)이 성공해도 전체 Run(작업)이 정상이라는 뜻은 아니다. sign-off(최종 검증) 성격의 판단에서는 빠른 표시보다 잘못된 결과를 정상으로 보이지 않는 것이 중요할 수 있다. 공개 업무 근거 J0/J2/J3/V5는 반도체 로그·리포트 파싱과 데이터 가공 자동화를 연결한다. 이는 EDA result reliability(EDA 결과 신뢰성)를 engineering requirement(엔지니어링 요구사항)로 다룰 근거이며, 회사 내부가 OpenSTA(정적 타이밍 분석 도구), 같은 validator(검증기), 같은 신뢰 정책을 사용한다는 주장이 아니다.

## 3. Validation Pipeline(검증 파이프라인)과 책임 경계

```text
OpenSTA/Yosys(정적 타이밍 분석 도구/합성 도구)
  → exit code/stdout/stderr/raw report(종료 코드/표준 출력/표준 오류/원시 리포트)
  → Execution Validation(실행 검증)
  → Structural Validation(구조 검증)
  → Semantic Validation(의미 검증)
  → Provenance Validation(출처 검증)
  → Trust Decision(신뢰 판정)
  → Normalized Result(정규화 결과)
  → DB/API(데이터베이스/응용 프로그래밍 인터페이스)
```

| 단계 | 책임 | 책임 밖 |
| --- | --- | --- |
| Execution Validation(실행 검증) | 도구 종료, timeout/cancel/crash(시간 초과/취소/중단), 기대 산출물 존재, 관측된 execution outcome(실행 결과) | worker recovery(작업자 복구), 재시도·자원 스케줄링 정책 |
| Structural Validation(구조 검증) | 지원 profile(프로파일)의 필수 필드·중복·marker(완료 표식)·유한 수치·포맷·버전 | 숫자가 도메인상 같은 조건인지 판단 |
| Semantic Validation(의미 검증) | 분석 유형·단위·scope(범위)·corner(코너)·경로와 요약의 의미 일치 | 전체 design sign-off(설계 최종 검증) 통과 선언 |
| Provenance Validation(출처 검증) | 원문·입력·설정·도구·파서 버전의 추적 연결 | 저장 전략·조회 인덱스 최적화 |
| Trust Decision(신뢰 판정) | 소비 가능한 결과인지, 보류·거절 사유 | API(응용 프로그래밍 인터페이스) 화면·consumer(소비자)별 표현 정책 |

## 4. Execution Validation(실행 검증)

검증 질문은 tool(도구)이 정상 종료했는지, exit code(종료 코드)가 정상인지, timeout/crash/cancel(시간 초과/중단/취소)이 없는지, expected artifact(기대 산출물)가 생성됐는지, 실행 실패 뒤 남은 일부 report(리포트)를 정상 결과로 승격하지 않는지다.

| invariant(불변식) | 처리 |
| --- | --- |
| `exit_code != 0` | parsed timing data(파싱된 타이밍 데이터)가 있어도 trusted timing result(신뢰 타이밍 결과)로 자동 승격하지 않음 |
| execution failure(실행 실패)와 parsed data(파싱된 데이터) | 별도 축으로 보존; 데이터 존재가 실행 성공 증거를 대체하지 않음 |
| timeout/cancel(시간 초과/취소) | 실제 종료 확인 전에는 결과를 성공으로 판정하지 않음 |
| expected artifact(기대 산출물) 부재 | 정상 종료처럼 보이는 경우에도 trust(신뢰) 부여 금지 |

Deep Dive 1(첫 번째 딥다이브)은 process lifecycle/retry/worker recovery(프로세스 수명주기/재시도/작업자 복구)를 책임진다. 여기서는 관측된 execution outcome(실행 결과)이 result trust(결과 신뢰)에 어떻게 반영되는지만 다룬다.

## 5. Structural Validation(구조 검증)과 parser strategy(파서 전략)

구조 검증은 “리포트를 구조적으로 제대로 읽었는가”를 답한다. 지원 profile(프로파일)마다 required field(필수 필드), startpoint(시작점), endpoint(종점), path group(경로 그룹), path type(경로 유형), analysis type(분석 유형), slack(여유 시간), unit(단위), report scope(리포트 범위), duplicate field(중복 필드), truncated report(잘린 리포트), unsupported format/version(미지원 형식/버전), NaN/Infinity/malformed numeric value(비유한 값/손상 수치)를 명시한다.

| 후보 | 장점 | 한계·판별 기준 |
| --- | --- | --- |
| A. simple regex(단순 정규 표현식) | 작은 고정 포맷에서는 가장 작음 | section(구간)·중복·완전성 검증을 놓치면 기각 |
| B. regex + schema validator(정규 표현식+스키마 검증기) | 필드 계약을 명시 가능 | section(구간) 간 관계·순서 의미가 필요한지 비교 |
| C. section-aware parser(구간 인지 파서) | report structure(리포트 구조)와 summary/path(요약/경로) 관계를 표현 | 구현·유지 비용이 실제 오류 감소를 정당화하는지 비교 |
| D. structured output + validator(구조화 출력+검증기) | 텍스트 형식 의존성을 낮출 수 있음 | 실제 고정 OpenSTA(정적 타이밍 분석 도구) 버전·명령 profile(명령 프로파일)에서 지원·동등한 필드가 확인될 때만 비교 |

현재 근거는 OpenSTA(정적 타이밍 분석 도구) 3.1.0의 고정 text report(텍스트 리포트)다. 공식 command reference(명령 참조)는 structured output(구조화 출력) 후보를 언급하지만, 설치된 3.1.0·기록된 Tcl profile(명령 언어 프로파일)에서의 지원·필드 동등성은 미확인이다. 구현 전 별도 discovery gate(조사 관문)에서 명령, 버전, 출력, raw artifact hash(원시 산출물 해시)를 확인하며, 불가하면 text parser(텍스트 파서) 범위를 유지한다.

## 6. Semantic Validation(의미 검증)

Semantic Validation(의미 검증)은 숫자를 읽은 뒤 그 의미가 맞는지 검증하는 이 딥다이브의 도메인 축이다.

| semantic invariant(의미 불변식) | 금지하는 잘못된 해석 |
| --- | --- |
| setup(설정)과 hold(유지)를 같은 분석으로 혼합하지 않음 | 한 유형의 slack(여유 시간)을 다른 유형의 경고로 표시 |
| max path(최대 경로)와 min path(최소 경로)를 분리 | `min` report(리포트)를 setup/max(설정/최대)로 저장 |
| path group/startpoint/endpoint/clock domain(경로 그룹/시작점/종점/클록 도메인)을 보존 | 다른 경로의 결과를 같은 Finding(발견 항목)으로 취급 |
| corner/unit/report scope(코너/단위/리포트 범위)를 보존 | 다른 조건의 숫자를 같은 분석 결과로 비교 |
| WNS/TNS(최악 음의 여유/총 음의 여유)와 개별 path slack(경로 여유 시간)을 구분 | 특정 path slack(경로 여유 시간)을 design WNS(설계 최악 음의 여유)로 저장 |
| 일부 path result(경로 결과)와 전체 design result(설계 결과)를 구분 | `slack=-0.12ns` 하나로 전체 설계 실패를 단정 |

현재 OpenSTA(정적 타이밍 분석 도구) 실제 slice(슬라이스)는 setup/max(설정/최대) 단일 path(경로)만 지원한다. hold/min(유지/최소), WNS/TNS(최악 음의 여유/총 음의 여유), 복수 corner(코너)는 지원 주장이나 실제 결과가 아니라 mutation fixture(변형 고정 입력) 계약 후보로만 다룬다.

## 7. Provenance Validation(출처 검증)과 raw artifact(원시 산출물)

신뢰 가능한 Normalized Result(정규화 결과)는 raw artifact(원시 산출물)와 입력 조건까지 역추적할 수 있어야 한다.

| provenance field(출처 필드) | 역할 |
| --- | --- |
| run ID/attempt ID(작업/실행 시도 식별자), design/revision(설계/설계 버전) | 요청과 실행 이력 연결 |
| RTL/netlist/Liberty/SDC hash(레지스터 전송 수준/넷리스트/셀 라이브러리/설계 제약 해시) | 입력·분석 조건 식별 |
| OpenSTA/Yosys/parser/normalization schema version(정적 타이밍 분석 도구/합성 도구/파서/정규화 스키마 버전) | 해석·재파싱 계약 식별 |
| container image digest(컨테이너 이미지 다이제스트) | 컨테이너를 실제 채택했을 때만 실행 환경 식별 |
| raw report hash(원시 리포트 해시), command/analysis mode/corner/timestamp(명령/분석 모드/코너/시각) | 원문과 결과의 재현·감사 연결 |

저장 후보는 A. normalized data only(정규화 데이터만), B. raw report only(원시 리포트만), C. raw + normalized + parser/schema version(원시+정규화+파서/스키마 버전)이다. C는 baseline candidate(기준선 후보)이지만, storage cost(저장 비용), migration cost(마이그레이션 비용), retention policy(보존 정책)를 측정하기 전 최종 답으로 확정하지 않는다. Deep Dive 2(두 번째 딥다이브)는 이 필드를 저장·조회하는 schema/query(스키마/조회) 책임을 가진다. 이 계획은 trusted result(신뢰 결과)에 필요한 provenance(출처 추적) 계약만 정의한다.

## 8. Trust Model(신뢰 모델)과 failure taxonomy(실패 분류)

| 후보 | 장점 | 비용·검증 질문 |
| --- | --- | --- |
| A. Binary Model(이진 모델) `VALID/INVALID` | 소비가 단순 | partial/debug data(부분/디버그 데이터)와 원인을 충분히 표현하는가 |
| B. Multi-state Model(다중 상태 모델) `TRUSTED/PARTIAL/UNKNOWN/INVALID` | 현실 상태와 보류를 표현 | API/consumer(응용 프로그래밍 인터페이스/소비자)가 `PARTIAL`을 `TRUSTED`처럼 사용하지 않는가 |
| C. separated axes + derived trust(축 분리+파생 신뢰) | execution/parse/semantic/provenance(실행/파싱/의미/출처) 원인을 가장 명확히 보존 | 상태 조합과 derived rule(파생 규칙)를 관리할 수 있는가 |

기본 후보는 C이며 fail-closed(의심 시 차단)다. `TRUSTED`는 모든 필수 축이 지원 profile(프로파일)에 대해 유효하고 raw artifact(원시 산출물)와 필수 provenance(출처 추적)가 연결됐을 때만 허용한다. `PARTIAL`은 디버그·원인 분석에 노출될 수 있으나 설계 통과나 비교 가능한 결과로 사용하지 않는다. `UNKNOWN`은 실행·입력·출처가 불충분해 판정하지 못한 경우, `INVALID`는 명시 위반이 확인된 경우다.

| failure class(실패 등급) | 예시 | 기본 trust state(신뢰 상태) 후보 |
| --- | --- | --- |
| Execution Invalid(실행 무효) | `TOOL_EXIT_NONZERO`, `TIMEOUT`, `CANCELLED` | `INVALID` 또는 종료 미확정이면 `UNKNOWN`; `TRUSTED` 금지 |
| Structural Invalid(구조 무효) | `REPORT_TRUNCATED`, `FIELD_MISSING`, `MALFORMED_VALUE`, `UNSUPPORTED_FORMAT`, `UNSUPPORTED_VERSION` | `INVALID`, 원인 분석용 원문 보존 |
| Semantic Invalid(의미 무효) | `ANALYSIS_TYPE_MISMATCH`, `UNIT_MISMATCH`, `PATH_SCOPE_MISMATCH`, `CORNER_MISMATCH`, `SUMMARY_PATH_CONFUSION` | `INVALID`, 잘못된 정규화·비교 금지 |
| Provenance Invalid(출처 무효) | `INPUT_HASH_MISSING`, `TOOL_VERSION_MISSING`, `RAW_ARTIFACT_MISSING`, `CONFIG_MISMATCH` | `UNKNOWN` 또는 `INVALID`; consumer(소비자) 용도에 따른 사람 정책 필요 |

## 9. Mutation / Corruption Testing(변형 / 손상 테스트)

정상 actual OpenSTA report(실제 OpenSTA 리포트)를 원문으로 유지하고, 별도 fixture(고정 입력) 사본에서만 변형한다.

| 사례 | 변형 | 기대 불변식 |
| --- | --- | --- |
| Truncated Report(잘린 리포트) | 완료 marker(완료 표식) 또는 report section(리포트 구간) 삭제 | `TRUSTED` 금지 |
| Non-finite Value(비유한 값) | `slack=NaN/Inf` | `INVALID` |
| Unit Mutation(단위 변형) | ns(나노초)와 ps(피코초)·선언 단위 불일치 | semantic mismatch(의미 불일치) 거절 |
| Exit Failure + Valid-looking Report(종료 실패+정상처럼 보이는 리포트) | nonzero exit code(0이 아닌 종료 코드)와 유효 slack(여유 시간) | trusted result(신뢰 결과) 승격 금지 |
| Analysis Type Mismatch(분석 유형 불일치) | metadata(메타데이터)는 setup(설정), report(리포트)는 min/hold(최소/유지) | `INVALID` |
| Scope Mismatch(범위 불일치) | 개별 path slack(경로 여유 시간)을 WNS(최악 음의 여유)처럼 전달 | `INVALID` |
| Version Drift(버전 변화) | 지원하지 않는 tool/report version(도구/리포트 버전) | explicit reject/unknown(명시 거절/미확정) |
| Provenance Mutation(출처 변형) | Liberty/SDC hash(셀 라이브러리/설계 제약 해시) 변경 또는 누락 | trust/comparability(신뢰/비교 가능성) 영향 명시 |

## 10. Baseline(기준선)·Challenger(도전 대안)·Adoption Gate(채택 기준)

Baseline(기준선)은 현재 고정 OpenSTA(정적 타이밍 분석 도구) parser(파서)와 execution/parse/check(실행/파싱/검사) 분리다. Challenger(도전 대안)는 Section-aware Parser(구간 인지 파서), regex + schema validator(정규 표현식+스키마 검증기), 실제 버전에서 확인된 경우 structured output + validator(구조화 출력+검증기) 중 하나만 선택한다.

| 비교 지표 | 의미 |
| --- | --- |
| required field accuracy(필수 필드 정확도) | 지원 fixture(고정 입력) 원문·독립 oracle(검증 기준) 일치 |
| false trusted result count(거짓 신뢰 결과 수) | 무효·미지원·손상 입력을 `TRUSTED`로 만든 횟수 |
| false reject count(잘못된 거절 수) | 지원 정상 fixture(고정 입력)를 거절한 횟수 |
| explicit rejection coverage(명시 거절 범위) | mutation fixture(변형 고정 입력)에 사유가 남는 비율 |
| parser latency/complexity/maintenance cost(파서 지연/복잡성/유지 비용) | 안전성 이득의 비용 |
| version robustness(버전 견고성) | 미지원 버전을 조용히 오해석하지 않는지 |

순서는 `Invariant(불변식) → actual fixture correctness(실제 고정 입력 정합성) → mutation/corruption test(변형/손상 테스트) → baseline/challenger(기준선/도전 대안) → 비용 평가 → adoption gate(채택 기준)`다. 예시 채택 기준은 지원 fixture(고정 입력)의 required field mismatch(필수 필드 불일치) 0, false trusted result(거짓 신뢰 결과) 0, 무효·미지원 사례의 explicit reject/unknown(명시 거절/미확정), 정상 fixture regression(고정 입력 회귀) 없음, 허용한 실험 예산 안의 parser latency(파서 지연)다. 수치는 production SLA(운영 서비스 수준 협약)가 아니라 bounded experiment decision threshold(범위 제한 실험 판단 기준)다.

## 11. Trade-off(상충관계), 테스트, 관측성

| trade-off(상충관계) | 판별 질문 |
| --- | --- |
| strict rejection(엄격한 거절) vs useful partial data(유용한 부분 데이터) | 부분 데이터를 저장하되 consumer(소비자)가 신뢰 결과로 오용하지 않게 할 수 있는가 |
| binary trust model(이진 신뢰 모델) vs multi-state model(다중 상태 모델) | 원인 추적 이득이 상태 복잡성을 정당화하는가 |
| raw artifact retention(원본 산출물 보존) vs storage cost(저장 비용) | 재파싱·감사·재현 가치가 보존 비용을 정당화하는가 |
| strict version compatibility(엄격한 버전 호환성) vs forward compatibility(향후 버전 유연성) | 미지원 버전을 조용히 파싱하는 위험보다 호환성 이득이 큰가 |
| rich semantic validation(풍부한 의미 검증) vs implementation complexity(구현 복잡성) | 추가 규칙이 실제 false trust(거짓 신뢰)를 줄이는가 |
| fail-closed(의심 시 차단) vs fail-open(일부 허용) | sign-off(최종 검증)성 소비 경로에서 안전한 기본값은 무엇인가 |

구현이 승인되면 탐색 → bug/invariant(결함/불변식) 확정 → Red-Green-Refactor(실패-통과-정리) → Test Scope Review(테스트 범위 검토) → 필요한 실제 integration/fault-injection/contract test(통합/장애 주입/계약 테스트) 확장 순서로 진행한다.

| 테스트 | 최소 검증 |
| --- | --- |
| Unit Test(단위 테스트) | field parser(필드 파서), semantic rule(의미 규칙), trust derivation(신뢰 파생) |
| Integration Test(통합 테스트) | actual OpenSTA output(실제 OpenSTA 출력) → parser/validator(파서/검증기) → DB/API(데이터베이스/응용 프로그래밍 인터페이스) 계약 |
| Regression Test(회귀 테스트) | false-success(거짓 성공), malformed report(손상 리포트), 버전·단위·범위 결함 고정 |
| Fault Injection / Corruption Test(장애 주입 / 손상 테스트) | 종료 실패, 잘린 리포트, 단위 변형, 버전 불일치, 출처 누락 |
| Contract Test(계약 테스트) | trusted result(신뢰 결과)의 필드·상태 계약과 execution/parse/semantic/provenance(실행/파싱/의미/출처) 조합 |

Test Scope Review(테스트 범위 검토)는 synthetic fixture(합성 고정 입력)만 맞고 실제 report(리포트)에서 깨지는지, parser test(파서 테스트)가 semantic mismatch(의미 불일치)를 놓치는지, API contract(응용 프로그래밍 인터페이스 계약)가 `PARTIAL`을 `TRUSTED`처럼 소비하게 하는지, old parser/new report version(이전 파서/새 리포트 버전) 조합을 빠뜨리는지 확인한다.

Trace(추적)는 raw artifact ID(원시 산출물 식별자), parser span(파서 구간), semantic validator span(의미 검증기 구간), validation failure reason(검증 실패 사유), trust decision(신뢰 판정), parser/tool version(파서/도구 버전)을 연결한다. 목표는 “왜 이 결과가 `TRUSTED`가 아니었는가”를 trace/log/evidence(추적/로그/근거)로 설명하는 것이다.

## 12. CI/CD(지속적 통합/지속적 배포), 역할, 종료 조건

PR(풀 리퀘스트) 관문은 `unit/regression(단위/회귀) → parser mutation fixture(파서 변형 고정 입력) → actual OpenSTA fixture integration(실제 OpenSTA 고정 입력 통합) → schema/contract validation(스키마/계약 검증)`이다. Docker build(도커 빌드), staging(스테이징), actual minimal EDA smoke(실제 최소 EDA 간이 검증), deploy(배포)는 컨테이너·배포가 별도로 채택·승인된 경우에만 뒤에 추가한다. OpenSTA/parser version(정적 타이밍 분석 도구/파서 버전)이 바뀌면 parser/result contract regression(파서/결과 계약 회귀)을 검출한다. 운영 metric(운영 지표) 후보는 unknown/invalid rate(미확정/무효 비율), parser failure rate(파서 실패율), unsupported version count(미지원 버전 수), false-trust regression(거짓 신뢰 회귀)이다.

AI/Agent(인공지능/에이전트)는 fixture mutation(고정 입력 변형), parser challenger(파서 도전 대안) 초안, 반복 테스트, 결과 집계, failure matrix(실패 행렬), benchmark(벤치마크)를 지원할 수 있다. Human(사람)은 trusted result(신뢰 결과)의 의미, semantic invariant(의미 불변식), partial data(부분 데이터) 허용 범위, adoption gate(채택 기준), parser strategy(파서 전략), 종료 결정을 소유한다.

다음이 모두 충족되면 멈춘다.

1. actual OpenSTA report fixture(실제 OpenSTA 리포트 고정 입력)와 execution/structural/semantic/provenance validation boundary(실행/구조/의미/출처 검증 경계)를 설명할 수 있다.
2. 지원 fixture(고정 입력)에서 false trusted result(거짓 신뢰 결과)가 0이고, truncated/invalid/unsupported/non-finite(잘림/무효/미지원/비유한) 사례가 정상 결과로 승격되지 않는다.
3. setup/hold/path scope/corner(설정/유지/경로 범위/코너), raw artifact(원시 산출물)에서 normalized result(정규화 결과)까지의 provenance(출처 추적), trust model(신뢰 모델)의 trade-off(상충관계)를 설명할 수 있다.
4. baseline/challenger parser(기준선/도전 파서) 비교 근거와 CI(지속적 통합)의 parser/result contract regression(파서/결과 계약 회귀) 탐지 계획이 있다.
5. README(읽어보기 문서) 없이 15분 동안 이 딥다이브의 근거·결과·한계를 설명하고 Human Decision Gate(사람 결정 관문)에 실제 결과를 제시한다.

## 13. 세 딥다이브 경계와 기록 위치

| 딥다이브 | 책임 | 공통 수단의 역할 |
| --- | --- | --- |
| Deep Dive 1: Execution Reliability(첫 번째 딥다이브: 실행 신뢰성) | queue/worker/retry/recovery/resource/process lifecycle(대기열/작업자/재시도/복구/자원/프로세스 수명주기) | trace/testing/CI/CD(추적/테스트/지속적 통합·지속적 배포)로 실행 불변식 검증 |
| Deep Dive 2: Data Modeling & Query Optimization(두 번째 딥다이브: 데이터 모델링 및 쿼리 최적화) | schema/finding identity/comparability/query plan/index/migration(스키마/발견 항목 식별/비교 가능성/쿼리 실행 계획/인덱스/마이그레이션) | trace/testing/CI/CD(추적/테스트/지속적 통합·지속적 배포)로 결과 조회 의미·비용 검증 |
| Deep Dive 3: Result Correctness & Contract Validation(세 번째 딥다이브: 결과 정합성 및 계약 검증) | parse/semantic validation/provenance/trust decision/parser-version contract(파싱/의미 검증/출처 추적/신뢰 판정/파서 버전 계약) | trace/testing/CI/CD(추적/테스트/지속적 통합·지속적 배포)로 신뢰 결과 승격 금지 검증 |

공통 수단은 중복 구현 backlog(구현 백로그)가 아니라 각 딥다이브를 검증하는 수단이다. 프로젝트 repo(저장소)가 plan/evidence/decision(계획/근거/결정)의 source of truth(원본 기준)다. 실제 결과·원시 산출물 참조는 `docs/evidence/`, 사람 선택은 `docs/decisions/`에 기록한다. Career OS(커리어 운영체제)는 저장소 revision(리비전), 링크, 짧은 결과·한계 요약, 역량 연결만 유지하며 원시 근거와 결정 전문을 복제하지 않는다.
