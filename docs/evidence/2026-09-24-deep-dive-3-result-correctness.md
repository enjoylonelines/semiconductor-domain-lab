# Deep Dive 3(세 번째 딥다이브): 결과 정합성 및 계약 검증 근거

계획: [EDA Result Correctness & Contract Validation(EDA 결과 정합성 및 계약 검증)](../plans/2026-09-24-deep-dive-3-eda-result-correctness.md).

## 문제와 기준선

기준선 `ParseResult(파싱 결과)`와 `runs(작업)`에는 `parse_status(파싱 상태)`, `check_status(검사 상태)`, `completeness(완전성)`, `provenance(출처 추적)`만 있었다. 따라서 OpenSTA(정적 타이밍 분석 도구) report(리포트)가 구조적으로 읽히지만 setup/max(설정/최대) 계약과 다른 `Path Type: min`을 포함할 때 구조 오류와 의미 오류를 구분하지 못했다. service(서비스)는 결과가 소비 가능한 trusted result(신뢰 결과)인지도 저장하지 않았다.

## Red(실패)

새 계약 테스트는 다음 결과를 보였다.

- 정상 actual OpenSTA report(실제 OpenSTA 리포트)에 `semantic_status(의미 상태)`와 `provenance_status(출처 상태)`가 없어 실패했다.
- nonzero process exit(0이 아닌 프로세스 종료) 뒤 `trust_status(신뢰 상태)`가 없어 실패했다.
- `Path Type: max`를 `Path Type: min`으로 바꾼 같은 리포트는 `parse_status=INVALID(파싱 상태=무효)`가 되어, 구조적으로 읽을 수 있는 정보와 semantic invalid(의미 무효)를 분리하지 못했다.

이 기준선은 실제 OpenSTA(정적 타이밍 분석 도구) 원문 `normal.log`를 임시 사본에서만 변형했다. 기록된 원문과 실행 증거는 변경하지 않았다.

## Green(통과)

`ParseResult(파싱 결과)`에 다음 축을 추가했다.

- `semantic_status=VALID|INVALID|UNKNOWN(의미 상태=유효|무효|미확정)`
- `provenance_status=VALID|UNKNOWN(출처 상태=유효|미확정)`

`runs(작업)`은 두 축과 `trust_status=TRUSTED|INVALID|UNKNOWN(신뢰 상태=신뢰|무효|미확정)`를 보존한다. service(서비스)는 adapter-observed process exit(어댑터 관측 프로세스 종료), parse(파싱), semantic(의미), provenance(출처)를 조합해 trust(신뢰)를 결정한다.

| 사례 | 실행 | 파싱 | 의미 | 검사 | 신뢰 |
| --- | --- | --- | --- | --- | --- |
| 정상 `normal.log` | exit 0(종료 0) | `OK` | `VALID` | `PASS` | `TRUSTED` |
| 타이밍 위반 `tight.log` | exit 0(종료 0) | `OK` | `VALID` | `FAIL` | `TRUSTED` |
| nonzero exit(0이 아닌 종료) + 유효 리포트 | 실패 | `OK` | `VALID` | `PASS` | `INVALID` |
| `Path Type: min` 변형 | exit 0(종료 0) | `OK` | `INVALID` | `UNKNOWN` | `INVALID` |
| marker(완료 표식) 누락 | 결과 불완전 | `INVALID` | `UNKNOWN` | `UNKNOWN` | `INVALID` |

`TRUSTED(신뢰)`는 설계 check(검사)의 `PASS(통과)`를 뜻하지 않는다. `tight.log`는 실행·파싱·의미·출처 계약을 만족하므로 신뢰 가능한 결과이지만 timing check(타이밍 검사)는 `FAIL(실패)`로 보존된다.

## 검증

```sh
PYTHONPATH=src .venv/bin/python -m unittest tests/test_opensta_report.py -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Focused OpenSTA suite(집중 OpenSTA 테스트): 9개 통과. 전체 suite(전체 테스트): 32개 통과, 0.219초. 전체 suite(전체 테스트)는 기존 bounded batch test(제한 배치 테스트)에서 SQLite(라이트급 SQL 저장소) connection(연결) 미종료 `ResourceWarning(자원 경고)`를 출력했지만 실패하지 않았다. 이 slice(슬라이스)는 경고를 수정하거나 억제하지 않았다.

## 한계와 다음 Human Decision(사람 결정)

- 실제 도구 실행은 새로 수행하지 않았다. 보존된 OpenSTA(정적 타이밍 분석 도구) 3.1.0 원문과 adapter-observed exit(어댑터 관측 종료) test double(테스트 대역)를 사용했다.
- `provenance_status=VALID(출처 상태=유효)`는 현재 지원 profile(프로파일)의 raw report hash(원시 리포트 해시), tool/parser version(도구/파서 버전), report profile(리포트 프로파일) 연결을 뜻한다. RTL/netlist/Liberty/SDC hash(레지스터 전송 수준/넷리스트/셀 라이브러리/설계 제약 해시) 전체를 Run(작업)에 결합한 증거는 없다.
- hold/min(유지/최소), multi-corner(다중 코너), WNS/TNS(최악 음의 여유/총 음의 여유), structured output(구조화 출력)은 검증하지 않았다.
- 사용자는 `PARTIAL(부분)` 소비 정책과 모든 입력 hash(해시)를 신뢰 조건으로 승격할 시점을 결정해야 한다.
