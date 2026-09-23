# Stage 1 검증 증거

기준일: 2026-09-23

## 확인한 경로

- synthetic EDA adapter가 timing report artifact를 생성한다.
- parser가 fixture marker와 필드를 확인하고 `ps`를 `ns`로 정규화한다.
- `worst_slack < 0`이면 `check_status=FAIL`로 기록한다. 이는 파싱 성공과 설계 검증 통과를 분리하기 위한 규칙이다.
- JobService가 `QUEUED -> RUNNING -> SUCCEEDED/FAILED` 상태를 기록한다.
- 동일 `job_id` 재제출은 중복 실행 대신 기존 결과를 반환한다.
- HTTP API에서 `POST /jobs`는 `202`, `GET /jobs/{id}`는 저장된 상태·metrics·artifact 정보를 반환한다.

## 실행 결과

Max workspace에서 다음을 실행해 통과했다.

    PYTHONPATH=src python3 -m unittest discover -s tests -v

두 테스트가 통과했다.

1. parser: `-80 ps -> -0.08 ns`, `check_status=FAIL`
2. service: end-to-end 실행과 idempotency

HTTP smoke test도 `POST 202` 후 `GET`에서 `SUCCEEDED`, `parse_status=OK`, `check_status=FAIL`, metrics/artifact 경로를 확인했다.

## 해석의 범위

이 결과는 실제 EDA tool, Trace32, Aardvark, 라이선스 서버, 보드, 대규모 worker pool을 검증한 결과가 아니다. Synthetic adapter와 작은 SQLite/in-process worker로 “수집→파싱→저장→상태조회” 계약이 이어지는지만 확인한 것이다. 실제 tool 연동은 Stage 4의 별도 adapter와 자원 임대·락·timeout·cleanup 검증으로 남긴다.
