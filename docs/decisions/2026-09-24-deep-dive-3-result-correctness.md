# Decision(결정): Deep Dive 3(세 번째 딥다이브) 결과 신뢰 계약

근거: [결과 정합성 근거](../evidence/2026-09-24-deep-dive-3-result-correctness.md). 계획: [결과 정합성 계획서](../plans/2026-09-24-deep-dive-3-eda-result-correctness.md).

## 구현 결정

현재 지원 OpenSTA(정적 타이밍 분석 도구) 3.1.0 single-path setup/max(단일 경로 설정/최대) profile(프로파일)에서는 separated axes + derived trust(축 분리+파생 신뢰)를 채택했다.

- `execution_status(실행 상태)`는 adapter-observed process exit(어댑터 관측 프로세스 종료)에서 나온다.
- `parse_status(파싱 상태)`는 구조 수용 여부를 나타낸다.
- `semantic_status(의미 상태)`는 setup/max(설정/최대) 분석 계약과 summary/path(요약/경로) 관계를 나타낸다.
- `provenance_status(출처 상태)`는 지원 profile(프로파일)의 원문·도구·파서 연결을 나타낸다.
- `trust_status(신뢰 상태)`는 위 축을 소비 가능한 결과로 조합한다.

`check_status=FAIL(검사 상태=실패)`만으로 `trust_status=INVALID(신뢰 상태=무효)`가 되지 않는다. 실행·구조·의미·출처가 유효한 timing violation(타이밍 위반)은 신뢰 가능한 실패 결과다. nonzero exit(0이 아닌 종료) 또는 semantic invalid(의미 무효)는 리포트 숫자가 있어도 신뢰 결과가 될 수 없다.

## 보류된 사람 결정

1. `PARTIAL(부분)` 결과를 어떤 API(응용 프로그래밍 인터페이스) consumer(소비자)에게 보여줄지.
2. RTL/netlist/Liberty/SDC hash(레지스터 전송 수준/넷리스트/셀 라이브러리/설계 제약 해시) 전체가 없는 결과를 `UNKNOWN(미확정)`으로 낮출지.
3. hold/min(유지/최소), multi-corner(다중 코너), structured output(구조화 출력)을 다음 validation slice(검증 슬라이스)로 열지.

## Stop(중지)

이 bounded slice(범위 제한 슬라이스)는 actual report mutation(실제 리포트 변형) 한 개, 실행 종료 경계, trust persistence(신뢰 상태 저장)를 닫았다. Deep Dive 1(첫 번째 딥다이브)의 real subprocess lifecycle(실제 하위 프로세스 수명주기) 또는 Deep Dive 2(두 번째 딥다이브)의 schema/query(스키마/조회) 구현을 자동으로 시작하지 않는다.
