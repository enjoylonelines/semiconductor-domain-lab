# 재조사 결과와 프로젝트 범위 결정안

조사일: 2026-09-23  
상태: synthetic 프로토타입 / 2026-09-24 parser→service 반례 재현 / Product·Engineering STOP 미충족
목적: 도메인 학습 프로젝트와 EDA workflow 플랫폼 프로토타입의 경계를 정한다.

## 0. 현재 실행 계약 — 작은 제품 + Deep Dive 하나 (2026-09-24)

이 문서가 범위 정본이다. [학습 계획](domain-learning-plan-2026-09-23.md)은 Track A 이해 검증을, [Stage 1 decision](../architecture/stage1-decision.md)은 기존 prototype 선택을 보존한다. 아래 §3~8의 플랫폼/Day 1~3/100명 설명은 배경·조건부 후보이며 현재 실행 backlog를 뜻하지 않는다. 우선순위는 **아래 Product DoD 최소 작업 + 보고서 검증 Deep Dive 1개 → 두 STOP**이다.

### 현재 구현 수준과 7개 평가축

최초 commit 전 README/docs/src/tests 모두 untracked. 표준 HTTP API·SQLite·프로세스 내 worker·synthetic adapter가 있다. [9/24 재검증](../evidence/stage2-validation-matrix.md)에서 기존 5개 테스트는 통과했으나, 별도 probe가 종료 실패의 SUCCEEDED 저장과 비유한 slack의 PASS를 재현했다. 실제 EDA 출력 fixture·도구 실행은 아직 없다.

| 평가축 | 존재하는 근거 | 부족한 증거 |
|---|---|---|
| 문제정의/도메인 | 공식 과거 JD의 로그/리포트 파싱, 공개 STA 입출력 조사 | 사내 병목·포맷·반복 빈도, HW 담당자 확인 |
| 기술적 깊이 | parser→service의 두 반례와 원인 위치 | 실제 보고서·오류 fixture·대안 비교·수정 전후 측정 |
| 기술적 판단 | SQLite/단일 adapter 선택 기록, 실행/파싱/검사 구분 의도 | 그 계약의 실제 일관성; 선택 이유와 구현 보장을 동일시하지 않음 |
| 검증 증거 | 5 tests fresh pass, nonzero-exit/overflow 재현, 코드 hash | 실제 tool output correctness, 독립 oracle, 비용 측정 |
| 제품 완성도 | POST/GET와 내부 service 경로 존재 | 제3자 재현 README, export/오류 계약, 현재 false success 수정 |
| 운영 현실성 | worker 수 제한, synthetic retry 소진 | 내구성·대기열 admission·재시작·실제 자원/라이선스; 현 scope 밖 |
| Ownership/협업 | 소스/판단/실험 파일 | 사용자 독자 설명·리뷰 변경 이력·HW 피드백; AI 작성이나 용어 수를 대신 쓰지 않음 |

### Domain Reality / Reframing / 선택 이유

도메인 위치는 **디지털 회로의 STA(정적 타이밍 분석) 산출물 판독·정규화**다. `netlist(게이트 연결망) + Liberty(셀 타이밍 라이브러리) + SDC(타이밍 제약) → STA → timing report(타이밍 보고서) → SW 검증 → 사람이 결과 확인`을 다룬다. RTL 설계, 기능 simulation(시뮬레이션), 합성 자체, 전체 PPA(전력·성능·면적) 최적화, IP 통합 검증을 수행했다고 주장하지 않는다.

[출처 장부 V1~V5](../references/source-register-2026-09-23.md)의 공식 도구 문서와 **과거** SW Engineer 공고를 근거로 골랐다. 로그 파싱 업무와 직접 연결되고, 현재 parser에 재현 가능한 실패가 있으며, 단위·완전성·실행 상태의 정확도를 독립 측정할 수 있기 때문이다. 회사 내부에서도 같은 문제가 발생한다는 것은 가설이다. 한국어 용례는 기존 용어 계획을 사용하며 용어 암기는 제품 성과가 아니다.

“각 IP의 검증 플랫폼”에서 **“한 종류의 timing report가 실패·누락·수치 오류를 정상 결과로 보이게 하지 않도록 검증하고 원문까지 추적한다”**로 좁힌다. JEV식 재표현은 단일 성공/실패 대신 `execution × parse × check + completeness + provenance`를 평가 단위로 삼는 해석이다. Human hypothesis/Changed belief는 unrecorded. AI/challenger 가설은 이 경계만으로 잘못된 성공 해석을 막을 수 있다는 것이며 실제 사용자 시간 절감은 미검증이다.

### Product DoD / Product STOP

제품은 **단일 도구·단일 버전·단일 setup timing 보고서의 로컬 검증 도구**다. 기존 HTTP/worker는 재사용 가능한 demo 경로이지 새 기능 목표가 아니다. 실행형 또는 파일 replay형 하나를 README의 기본 경로로 정하되, 아래 actual-output gate는 동일하다.

- 제3자가 README대로 의존성/명령/버전을 고정하고 허가된 실제 공개 design 또는 tool-generated report를 입력해 정규화 결과·원문 위치를 확인한다. replay형이면 “공개 출력 재생”과 “직접 EDA 실행”을 구별한다.
- 실행 상태, 파싱 완전성, 해당 검사 상태가 분리되고, 종료 실패·누락·지원하지 않는 형식·비유한 숫자는 성공으로 포장되지 않는다. 정상·음수 slack·오류의 사용 경로를 재현한다.
- 입력 hash·tool/version·명령/분석 종류·단위·조건·report 범위·parser version을 보존하고 결과를 다시 확인/내보낼 수 있다. 체크 PASS는 해당 보고 범위에만 적용하며 chip sign-off가 아니다.
- 재현 명령·관련 테스트·실제 fixture 결과·알려진 한계가 연결되면 **Product STOP**. 지금은 false success와 actual-output/재현 안내가 없어 미충족이다.

### Deep Dive Target / invariant / vertical experiment

**단 하나: 불완전한 timing 결과를 정상으로 승격하지 않는 parser→service 경계.** job scheduler·분산 resource pool은 두 번째 Deep Dive로 추가하지 않는다.

| 단계 | 최소 작업과 남길 증거 |
|---|---|
| 1. 재현 | 기존 nonzero-exit/overflow probe를 `tests/test_stage1.py`의 실패 회귀로 고정. 누락 입력의 INVALID/UNKNOWN 대조도 보존 |
| 2. 내부 원인 | parser의 float/단위/필수 필드 처리와 service의 상태 매핑을 추적. tool 종료·보고 범위·유한 수치의 관계를 표로 고정 |
| 3. 실제 fixture gate | 아래 도구 선택 gate 후 공개 design/report 1개 계열과 원본 hash·출처·license·version·명령 확보. original과 truncation/duplicate/단위 변형 파생본을 분리 |
| 4. baseline/대안 | 기존 synthetic parser를 regression baseline으로 보존. 실제 형식에는 (A) 명시적 report 구문 parser+schema validator와 (B) 해당 버전이 제공하는 structured output+동일 validator를 비교. B 미지원이면 미지원으로 기록. 임의 regex로 얻은 숫자만 oracle로 삼지 않음 |
| 5. 구현·실패 시험 | 하나의 경로만 선택해 상태 매핑/유한값/출처 검증. 정상 양수·음수·실행 실패·truncated·중복·미지원 단위/version·같은 수치 다른 조건을 시험. 실제 양수/음수 출력과 인공 결함을 분리 |
| 6. 측정·판정 | 고정 fixture에서 필드 정확도와 false-success/false-PASS 수, 명시적 거부 coverage, 동일 입력 반복의 안정 필드 일치, 시간/메모리, 변경량·유지보수 비용을 전후 기록. 도구 실행 시간과 parser 시간을 분리 |
| 7. STOP | 범위 내 원인·비교·한 구현·edge test·실제 fixture·측정·한계가 연결되면 Engineering STOP. 반례가 없어진 5개 시험만으로 종료하지 않음 |

불변식: 유한 숫자와 확인된 단위만 정규화한다. 실행 실패는 run success가 아니다. 누락/잘림/미지원은 0/PASS가 아니다. 보고서 일부 경로의 slack을 전체 design의 worst slack으로 부르지 않는다. 원문 수치·단위·분석 범위와 정규화 결과를 역추적할 수 있어야 한다. runtime 경로에 expected label을 넣지 않는다.

정확도 oracle은 수동 검토한 원문 필드와 도구 자체 결과를 대조한다. 모든 **지원 fixture**의 필수 필드 일치·false-success 0·실패/미지원의 명시 판정 100%를 bounded acceptance로 삼되 일반 입력 정확도라고 부르지 않는다. 시간은 실제 파일 크기/행 수·3회 워밍업 후 20회 반복의 median/range를 기록하는 초기 제안이며 반복은 독립 design 수가 아니다. 속도 개선 주장은 같은 환경/입력에서만 한다. 운영 p95 목표를 임의로 만들지 않는다.

### 도구/실제 데이터 선택 gate와 AI 경계

환경은 [출처 장부의 확인 범위](../references/source-register-2026-09-23.md)에 한정된다. 로컬 PATH에서 STA 실행파일을 찾지 못했지만 전체 설치·Docker 실행 가능 여부는 미확인이다. **OpenSTA는 가장 작은 후보이지 채택 확정이 아니다.** 공식 example의 netlist/Liberty/constraints와 report 생성 경로를 먼저 확인한다. native/기존 container 자산 중 준비 비용이 작은 경로를 고르고, 설치 전에 tool revision·fixture 라이선스·architecture 호환·재현 명령을 고정한다. 전체 OpenROAD 합성/P&R 환경은 필요성이 입증되기 전 제외한다.

공식 문서의 `report_units`와 report 종류를 대조한다. `report_wns`와 `report_worst_slack`은 같은 값 정의가 아니며 출력 단위·버전·선택한 path 범위를 고정한다. structured output 제공 여부도 실제 버전에서 확인한다. 직접 실행이 막히면 provenance가 있는 공개 실제 출력으로 parser 검증을 진행할 수 있으나 실행 재현은 BLOCKED로 남긴다. mock만 있으면 두 STOP의 실제 fixture 조건은 미달이다.

LLM/Agent는 현재 불필요하므로 추가하지 않는다. deterministic validator로 처리할 수 없는 반복적인 의미 분류 실패가 실제 corpus에서 확인될 때만 별도 baseline 비교를 연다. 그때에도 correctness/실패·재현성/latency/cost/유지보수 trade-off를 같은 holdout으로 측정하고 이득 없으면 기각한다. 규격/수치/실행 성공의 결정 권한을 모델에 주지 않는다.

### Non-goals / Expansion Trigger / 다음 실제 구현 1개

Non-goals: 상용 EDA/실물 장비·회로 설계·sign-off, 여러 IP/format, PPA 최적화, 대규모 regression scheduler, 100명 운영, 새 UI/DB/broker, AI 도입. 현재 report validity를 입증하는 데 필요하지 않다. 도메인 학습은 넓게 하되 제품은 위 한 경계만 책임진다.

확장은 **핵심 가설 또는 Product/Engineering STOP을 막는 증거**가 있어야 한다. 잘못된 성공 표시는 지금 해결 대상이다. 두 번째 format은 실제 사용 사례의 필수 입력이 현재 계약으로 표현되지 않을 때, 자원 구조는 고정 workload의 실제 병목일 때만 별도 채택한다. 실제 공개 output 확보는 새 인프라 확장이 아니라 이번 STOP의 필수 검증이다. 미해결 상태·예산 만료는 성공 완료와 구별한다.

**다음 코드 작업 1개:** `tests/test_stage1.py`에 “tool_exit_code=1인데 service가 SUCCEEDED로 저장하는 반례”를 고정하고, 실패 의미를 보존하는 최소 상태 매핑 수정 후 같은 테스트로 재확인한다. 이 한 작업을 닫은 뒤 같은 Deep Dive 안의 실제 fixture gate로 진행한다. 이번 검토에서는 재현까지만 했으며 제품 수정은 하지 않았다.

최종 포트폴리오는 “어떤 STA input/output을 직접 다뤘는가?”에 fixture·명령으로, “무엇을 깊게 검증했는가?”에 parser/service 반례·수정 전후 표로 답한다. 사용자 독자 설명과 동료/HW 피드백은 확보한 경우에만 별도 증거로 남긴다.

## 0.1 Human-Owned / AI Delegation — 2026-09-24

| 영역 | Human-owned Knowledge / 판단 | AI 활용 | 검증 |
|---|---|---|---|
| 문제·도메인 | STA 입력/출력 위치, 종료코드·slack·단위·보고 범위, 실패를 성공으로 보이면 안 되는 이유 | 공식 출처/원문 위치 탐색, 용어 정리 | 실제 output을 자기 말로 설명; synthetic 한계 구분 |
| invariant·대안 | 실행 실패 ≠ run success, 수치 유한성; 실패 보고서 수치 보존과 UNKNOWN 처리의 차이 | 상태표·반례·A/B 후보 초안 | parser→service→저장 상태 독립 대조 |
| 구현 | parser 필수 필드/float/단위, service 분기와 attempts·metrics 저장 경로 | fixture/test/harness·선택된 최소 수정 | 코드 읽기·작은 변경·회귀 |
| 측정·주장 | false-success 분모, 실제 fixture oracle, 반복 안정성의 의미 | 반복/JSON 집계·보고서 | 실측과 예상 비교; sign-off·실제 EDA 실행 과장 금지 |

**Specification 초안:** Problem=nonzero tool exit를 service가 SUCCEEDED로 저장함. Constraint=기존 synthetic adapter/상태축·DB 유지, scheduler/도구 설치 제외. Invariant=tool_exit_code≠0이면 run/attempt 성공으로 저장하지 않음. Acceptance=같은 상태 matrix에서 false-success 0, 정상·음수 slack·누락 대조 보존. Failure=실패가 성공으로 저장되거나 parse 실패를 정상 체크로 승격하거나 정상 대조가 깨짐. 실패 보고서의 check/metrics 보존 정책은 Human Decision Gate 미정이다.

**핵심 코드:** `src/eda_lab/parser.py::parse_report`, `service.py::JobService._execute`, `store.py::get_run`과 `tests/test_stage1.py`. AI 작성 여부의 개별 provenance는 확인하지 않았지만 작성자와 관계없이 이 흐름은 본인이 이해해야 한다. 실제 STA output/단위 원문 대조와 사용자 독자 설명은 아직 증거가 없다.

**첫 실험:** `tools/exit_status_probe.py` + `tools/exit_status_prediction.example.json`을 준비했다. 기존 양수/nonzero 반례는 이미 공개된 baseline이다. 새 Prediction은 nonzero+음수, nonzero+slack 누락, 정상 양수 대조의 parser/check/run/attempt 상태를 먼저 적는다. example의 빈 칸을 본인 말로 채워 별도 prediction JSON으로 저장한 후 저장소 root에서 실행:

```sh
PYTHONPATH=src python3 -B tools/exit_status_probe.py --prediction-file /absolute/path/to/my-prediction.json
```

stdout JSON에 입력 원문/hash, code hash, 사전 기록, 관찰 시각, parser·run·attempt·metrics, elapsed, false-success와 예측 일치 여부가 남는다. **관찰용 harness이며 제품 수정/회귀 통과가 아니다.** 실행코드 1은 후보 invariant 위반, 0은 이 작은 matrix에서 위반 미관찰, 2는 입력/실험 오류다. 정상 대조까지 포함한 Acceptance와 정책은 사람이 대조한다. 시간은 탐색값이며 성능 우월성 지표가 아니다. 이번 추가 작업은 실행 전 준비이며 결과·Human decision은 pending이다.

**다음 실제 작업 1개:** Human Problem/Decision/Prediction 기록 → 이 probe 실행 → Evidence Gate에서 결과 해석 → 채택한 상태 계약의 실패 회귀와 최소 매핑 수정. 새로운 문서·scheduler 구현을 먼저 하지 않는다. AI가 줄이는 fixture/수집/정리 시간을 종료·파싱·검사 상태의 차이, 실제 STA fixture 판독에 재투자한다. [역할 분담](ai-human-division.md)은 이 계약을 따른다.

### Human Gates와 학습 종료조건

아래 명세는 **AI 제안**이며 사용자가 자기 말로 Problem·Constraint·Invariant·Acceptance·Failure 다섯 항목을 기록하기 전에는 전체 구현을 위임하지 않는다. 기존 계획의 가설·선택이나 AI 작성 문서를 사용자의 판단으로 소급하지 않는다. 현재 본인 숙지 증거와 새 Gate 기록은 **unrecorded**이며 지식이 없다고 단정하지 않는다.

순서: AI 자료/코드 탐색 → **Problem Gate**(문제·범위·불변식 설명) → AI 대안 → **Decision Gate**(차이·제약·실패·선택 이유) → **Prediction Gate**(실행 전 예상 상태/이유/반증을 시각·revision과 기록) → AI 구현·자동화 → 실행 → **Evidence Gate**(예상 대비 결과·증명 범위·추가 실험 필요 판단) → AI 집계/문서 → **Defense Gate**. 기존 decision/evidence 기록에 사용자 원문과 AI 후보를 분리한다. 이미 본 결과는 사전 예측으로 쓰지 않는다. 준비용 fixture/harness 초안은 가능하지만 채택/실행/사람 판단 완료와 구분한다.

**Engineering STOP 추가:** 아래 Deep Dive를 AI·README·메모 없이 약 15분 동안 문제→도메인/runtime→현재 코드 흐름→실패→대안/선택→시험 설계→실제 결과→한계/확장 조건 순으로 설명한다. 핵심 코드를 읽고 작은 변경을 직접 수행하며 실행 전에 영향·디버깅 방향을 설명한다. 기존 Product STOP과 측정 범위는 그대로 유지하며 사람의 설명 증거를 코드 테스트 통과로 대체하지 않는다.

학습 우선순위는 “이 코드/기술이 핵심 engineering claim을 성립시키는가?”로 좁힌다. YES인 runtime 동작만 공식 문서/필요한 source·test → 최소 재현 → 사전 예측 → 실행 비교로 확인한다. 나머지 CRUD/UI/서식은 AI 초안과 검토로 처리한다. 절약 시간이나 숙련도 개선은 측정 전 수치로 주장하지 않는다.

## 1. 이번 재조사에서 확인한 사실

### 회사 사업·제품

- 퀄리타스 공식 제품 페이지는 SERDES PHY, PCIe Gen4~Gen6 PHY, UCIe PHY, MIPI C/D-PHY 및 카메라·디스플레이·USB·Ethernet 관련 IP를 소개한다.
- 회사 공식 페이지는 MIPI PHY와 CSI-2/DSI-2 Controller를 결합한 subsystem, PHY와 Controller의 함께 검증된 제공 형태를 설명한다.
- 회사의 공시 자료는 제품군을 MIPI, Display Chipset, PCIe, Multi-level Signaling SERDES, UCIe 등 인터페이스 IP로 구분하고, SERDES가 SoC 내부 병렬 데이터를 직렬화하는 핵심 기술이라고 설명한다.
- 공식 EDA/채용 팀 소개는 EDA 개발 환경의 도입·구축·관리·운영 업무가 존재함을 보여준다.

출처:

- https://q-semi.com/kr
- https://www.q-semi.com/user/hisp/HIPC1000V
- https://www.q-semi.com/qaview.php
- https://kind.krx.co.kr/external/2026/03/19/20260319005557/11011.htm
- https://q-semi.career.greetinghr.com/ko/teams

### SW Engineer 업무

공식 과거 공고와 채용 플랫폼의 공고에서 다음 업무를 확인했다.

- RESTful API
- 메시지 큐 기반 비동기 이벤트
- 관계형 DB 설계·데이터 모델링·쿼리 최적화
- Redis Pub/Sub 실시간 전송
- 반도체 파일 포맷의 로그·리포트 파싱과 데이터 가공 자동화
- 컨테이너 기반 운영
- DB migration, 레거시 리팩토링, CI/CD
- 반도체·EDA·IP 도메인 지식 및 테스트 코드 우대
- 과거 공고의 HW 요구사항 반영 in-house tool, HW 개발자와의 협업, 업무 자동화, MCU firmware, Web programming

출처:

- https://q-semi.career.greetinghr.com/ko/o/212725
- https://www.wanted.co.kr/wd/368416
- https://www.wanted.co.kr/wd/217418

### 공개 자료로 확인할 수 없는 것

다음은 공개 자료에서 회사 내부 사실로 확인하지 못했다.

- 실제 EDA vendor와 실행 명령
- 실제 로그·리포트 포맷과 파일 보존 정책
- 실제 queue/scheduler와 worker 수
- 실제 DB 스키마와 사용자 수
- 100명이 의미하는 동시 사용자·동시 EDA job·파일량
- 실제 IP별 업무 분장과 HW 엔지니어 모니터링 방식

따라서 아래 프로젝트는 회사 내부 시스템 복제품이 아니라 공개 업무를 근거로 한 학습·설계 검증용 프로토타입으로 정의한다.

## 2. 재조사에 따른 핵심 결론

### 결론 A — 도메인 연결은 타당하다

EDA/IP 개발 결과를 로그·리포트·결과 파일로 다루고, 이를 파싱·저장·검색·자동화하는 SW 역할은 공고에 직접 연결된다.

### 결론 B — “각 IP의 설계 검증 플랫폼”은 너무 넓다

실제 Controller·PHY의 회로 설계와 검증은 HW/IP/verification 조직의 업무다. SW가 직접 담당하는 범위는 실행 조율, 결과 수집, 파싱, 이력 관리, API·알림·자동화에 가깝다.

### 결론 C — 100명과 동적 자원 풀은 별도 검증 목표다

100명이라는 사용자 수만으로는 운영 규모를 정의할 수 없다. 최소한 다음을 명시해야 한다.

- 동시 사용자 수
- 동시 EDA job 수
- 대기 job 수
- 평균·최대 실행 시간
- 결과 파일 크기
- worker·라이선스 제한
- 재시도와 취소 정책
- 사용자·팀별 quota
- 보존 기간

### 결론 D — 2~3일 계획은 플랫폼 완성이 아니다

2~3일은 도메인 학습과 synthetic 단일 flow vertical slice에 적합하다. 실제 EDA adapter, 여러 IP, 동적 worker pool, 100명 부하를 모두 구현하는 일정으로 사용하지 않는다.

## 3. 프로젝트를 두 트랙으로 분리

### Track A — 도메인 학습·검증

목표: 퀄리타스 SW Engineer 업무와 반도체/IP/EDA 흐름을 설명할 수 있게 한다.

산출물:

- Domain Map
- 디지털·아날로그·PHY EDA workflow
- 용어집
- JD mapping
- synthetic timing report parser
- 5분 면접 설명

종료 조건:

- SoC/IP/PHY/SerDes/PCIe/UCIe/MIPI 관계 설명
- EDA 산출물과 SW 접점 설명
- parser 1개와 실패 사례 검증
- 사실·추론·미확인 구분

### Track B — EDA workflow platform prototype

목표: “실제 EDA를 대신 실행하는 제품”이 아니라, 작업 등록부터 결과 모니터링까지의 경계를 검증한다.

1차 범위:

- 하나의 synthetic EDA flow
- 하나의 IP/flow adapter
- job HTTP API (현 Stage 1 선택: 표준 라이브러리 HTTP; FastAPI 전환은 필수 아님)
- queue와 worker
- 로그·리포트·결과 수집
- parser와 정규화된 Metric
- 개발 DB (현 Stage 1 선택: SQLite; PostgreSQL 전환은 측정 근거가 있을 때만 검토)
- 상태 조회 API
- 간단한 실시간 상태 전달
- retry/idempotency
- 실행·파싱·검사 상태 분리
- 부하 한계를 문서화

1차 비범위:

- 실제 proprietary EDA 실행
- 여러 IP의 완전한 지원
- GUI 대시보드 완성도
- 자동 sign-off 판정
- 실제 라이선스 스케줄링
- Kubernetes급 autoscaling
- 100명 운영 보장
- 보안·권한·감사 체계의 완성

## 4. 권장 아키텍처

    API
      ↓
    Job Service
      ↓
    Queue
      ↓
    Resource Policy
      ↓
    EDA Adapter
      ↓
    Synthetic Runner
      ↓
    Artifact Store
      ↓
    Parser Plugin
      ↓
    Run / Artifact / Metric DB
      ↓
    Query API + Status Events

### 경계별 계약

#### JobRequest

- job_id
- design_id
- ip_family
- flow_name
- input_ref
- requested_resources
- priority

#### JobState

- QUEUED
- RUNNING
- SUCCEEDED
- FAILED
- CANCELLED

#### ParseState

- NOT_STARTED
- OK
- PARTIAL
- INVALID

#### CheckState

- PASS
- FAIL
- UNKNOWN

JobState가 SUCCEEDED여도 CheckState는 FAIL일 수 있다.

#### EDA Adapter

    submit(job_spec) → adapter_job_id
    poll(adapter_job_id) → execution_state
    collect(adapter_job_id) → artifact_manifest
    parse(artifact_manifest) → normalized_result

다음 adapter를 추가할 수 있는 구조만 만들고, 실제로는 SyntheticTimingAdapter 하나만 구현한다.

## 5. 2~3일의 실제 구현 범위

### Day 1 — 수직 흐름

- JobRequest 저장
- queue에 등록
- worker가 synthetic report 생성
- artifact 저장
- parser 호출
- DB에 Run·Artifact·Metric 기록
- 결과 조회 API

수락 조건:

    POST /jobs
    → GET /jobs/{id}
    → GET /jobs/{id}/artifacts
    → GET /jobs/{id}/metrics

정상 실행 한 건이 처음부터 끝까지 흐른다.

### Day 2 — 실패·상태·관찰성

- 누락 report
- 잘못된 단위
- 중복 이벤트
- worker timeout
- retry 1회
- cancel 상태
- 원문 줄 번호·체크섬 보존
- 간단한 status event
- 구조화 로그

수락 조건:

- 실행 상태와 검사 상태가 섞이지 않는다.
- 실패 원인을 재현할 수 있다.
- 같은 이벤트를 두 번 받아도 중복 결과가 생기지 않는다.

### Day 3 — 범위 확장 준비와 제한 부하

- EDA Adapter 인터페이스 추출
- IP/flow별 parser registry
- worker 동시성 설정
- queue 길이·처리 시간·실패율 측정
- 동시 job 10~20개 부하 테스트
- 100명 목표에 필요한 추가 조건 문서화

수락 조건:

- 하나의 adapter를 교체할 수 있다.
- 부하 테스트 결과를 숫자로 남긴다.
- 100명 운영을 주장하지 않고 검증하지 않은 항목을 명시한다.

## 6. 100명·유동적 풀의 단계적 검증

아래는 조건부 확장 후보이며 자동 실행 순서가 아니다. §0의 핵심 가설이 검증되면 멈춘다. 단계별 필요성·workload·수락 기준이 별도로 결정된 경우에만 해당 검증을 연다.

### 단계 1: 기능 증명

- 사용자 1명
- 동시 job 1~2개
- 결과 파일 작음
- synthetic runner

### 단계 2: 서비스 흐름

- 동시 사용자 요청 20개
- 동시 job 5~10개
- queue 대기·재시도·중복 방지

### 단계 3: 제한 부하

- 가상 사용자 100명
- 동시 job 10~20개
- 결과 파일 크기와 처리 시간을 고정
- API p95, queue 대기시간, worker 처리량, 실패율 측정

### 단계 4: 실제 운영 후보

- 실제 EDA adapter
- license/resource quota
- IP별 실행시간 차이
- worker autoscaling
- artifact 보존·삭제
- 권한·감사·장애 복구

단계 3을 통과해도 실제 EDA 운영 성능을 증명한 것은 아니다. 단계 4까지 가야 운영 주장을 검토할 수 있다.

## 7. 재고관리·온톨로지와의 관계

재고관리와 온톨로지 보강은 이 프로젝트의 핵심 도메인이 아니다.

재사용 가능한 부분:

- 리소스 ID와 상태 관리 개념
- 이벤트·이력·정합성 모델
- 자원 할당과 quota 개념
- 작업·결과·관계 데이터를 추적하는 방식

분리할 부분:

- 재고 도메인 테이블을 EDA 테이블에 직접 섞지 않음
- 온톨로지의 일반 이벤트 모델을 EDA 결과 의미로 그대로 간주하지 않음
- 각 프로젝트의 README와 acceptance criteria를 별도로 유지

## 8. 최종 포트폴리오 주장 문장

구현 전에는 다음만 주장한다.

> 공개된 퀄리타스 사업·채용 자료를 바탕으로 EDA 작업의 실행·산출물·SW 처리 접점을 분석하고, synthetic EDA-like flow에서 작업 등록, 결과 수집, 파싱, 저장, 상태 모니터링의 최소 경로를 검증하는 계획을 세웠다.

Track B를 완료한 뒤에는 다음처럼 말한다.

> 실제 EDA 도구를 복제하지 않고 adapter 경계를 두어 synthetic flow를 실행했다. 로그·리포트·결과를 수집하고 Run·Artifact·Metric으로 정규화했으며, 실행 상태·파싱 상태·검사 상태를 분리했다. 제한된 동시 job 부하에서 queue와 worker의 동작을 측정했다.

다음 표현은 검증 전에는 사용하지 않는다.

- 100명 운영 가능
- 실제 EDA 인프라 구축
- 각 IP 검증 자동화 완료
- 회사 내부 workflow 재현
- 동적 resource pool이 production-ready

## 9. 다음 결정

아래는 초기 선택지다. 현재 Track B 코드가 존재하므로 다시 초기 구현을 시작하지 않는다. 다음 결정은 기존 evidence로 §0의 종료조건을 판정하고, 부족한 범위 내 증거만 보완할지 여부다.

1. **Track A만 진행:** 도메인 학습과 parser까지 완료
2. **Track A + Track B 최소 vertical slice:** synthetic flow를 포함한 API·queue·parser·DB·모니터링 구현

현재 우선순위는 §0의 단일 timing report 검증과 Product/Engineering STOP이다. 다음 코드는 nonzero-exit의 service 성공 오표시 회귀·최소 수정 1개다. 실제 공개 tool output은 필수 증거이며 100명 운영·추가 adapter·인프라는 후속 결정 없이 진행하지 않는다.
