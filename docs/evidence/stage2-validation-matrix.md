# Stage 2 검증 매트릭스

아래 표는 초기 Stage 2 점검 기록이다. 최신 판정은 하단 **2026-09-24 재검증**을 따른다. Stage 3 smoke 존재와 실패 의미의 검증 완료는 다르다.

| 경로 | 현재 증거 | 판정 |
|---|---|---|
| 정상 실행 | parser/service unittest + API smoke | 확인됨 |
| 중복 제출 | service test가 동일 job_id 결과 재사용 확인 | 확인됨 |
| 잘못된 report | parser unit test 일부 | 부분 확인 |
| retry exhaustion | 현재 service의 최대 시도 횟수와 timeout 시험 존재; 9/24 기존 테스트 통과 | synthetic timeout 소진만 확인, 실제 tool 종료 실패와 별개 |
| worker interruption | 아직 프로세스 재시작 실험 없음 | 지원하지 않음으로 문서화 |
| cancel race | queued cancel 메서드만 구현, 실행 중 취소 불가 | 제한 명시 |
| restart recovery | SQLite 재시작 복구를 보장하지 않음 | 지원하지 않음 |

## Stage 3 진입 조건

- 실패를 재시도 횟수와 함께 기록한다.
- 시도별 artifact 경로가 덮어써지지 않는다.
- 작업 중단 시 `RUNNING`을 성공이나 취소로 오표시하지 않는다.
- 지원하지 않는 재시작 복구와 실행 중 취소는 API 계약에서 명시적으로 거부한다.
- 테스트 결과를 현재 workspace 상태와 함께 다시 기록한다.

## 2026-09-24 재검증 — 기존 테스트 통과와 별도 반례

DevSpace Max `ws_efc7c3708c`, `semiconductor-domain-lab`, 최초 commit 전 untracked 소스. 제품 수정 없이 수행했다. 명령 `PYTHONPATH=src python3 -B -m unittest discover -s tests -v`: **5 tests / 0.357s / OK**. 이는 합성 데이터의 기존 단위·service 테스트이며 HTTP E2E나 실제 EDA 출력 검증이 아니다.

| 최소 입력/경로 | 관측 | 판정 |
|---|---|---|
| 정상 synthetic 헤더 + tool_exit_code=1 + worst_slack=0.12 ns → parser → service | parser metrics.job_status=FAILED, parse=OK, check=PASS; service job=SUCCEEDED | 실행 실패의 서비스 상태 반영 누락. Product STOP 차단 |
| tool_exit_code=0 + 400자리 숫자9 + ns → parser | slack=inf, parse=OK, check=PASS | 유한 수치 invariant 위반. Engineering STOP 차단 |
| 필수 worst_slack 누락 → parser | INVALID/UNKNOWN, missing field worst_slack | 현재 거부 동작 확인. PARTIAL 지원 증거는 아님 |

재현은 임시 파일에 기존 synthetic header/version/run_id/stage/corner와 표의 필드를 기록하고 `parse_report`를 호출했다. 첫 사례는 같은 파일을 반환하는 시험 adapter로 `JobService(Store(), max_workers=1)`에 제출하고 future 종료 후 `get("probe")`를 조회했다. DB는 in-memory, 외부 도구/계정/실데이터 사용 없음. 400자리 입력은 overflow 경계용 인공 반례이며 실제 보고서 발생 빈도를 뜻하지 않는다.

원인: parser는 `float` 변환 후 finite 검사가 없고, service는 parser가 INVALID가 아니면 report의 tool 종료 실패와 무관하게 SUCCEEDED를 쓴다. 개별 timing 숫자의 부호와 실행 완료/보고서 완전성은 서로 다른 증거다. 실패 실행의 일부 수치가 양수여도 전체 run을 성공으로 승격해서는 안 된다.

코드 SHA256:
- parser.py: `b78d00410c48625b69c73390639d70646780466c16f703f5f259c73195a65115`
- service.py: `b7f558636165105ce9ac25eb37a3dfd12a2bd94dfad69fba4faee8ccb0a71e0e`
- tests/test_stage1.py: `0a93a670133e8563799af62e69b08d10aaab0b4b34e4659623550eab059cdb0f`

이번 결과는 failure reproduction까지다. 수정·before/after·실제 fixture 검증·latency/메모리 측정은 미실행이다. 다음 코드 작업과 두 STOP은 [범위 정본](../plans/research-and-scope-2026-09-23.md)의 vertical experiment를 따른다. 기존 5개 테스트 통과를 제품 완성이나 엔지니어링 깊이의 충분한 증거로 쓰지 않는다.
