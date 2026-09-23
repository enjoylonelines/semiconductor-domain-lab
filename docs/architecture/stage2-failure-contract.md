# Stage 2 결정: 실패·재시도·관측성

Stage 1의 목적은 한 번의 정상 경로를 끝까지 잇는 것이었다. Stage 2에서는 운영 실패를 먼저 모델링한다.

## 결정

- `parse_status`와 `check_status`는 `execution_status`와 분리한다.
- 재제출은 `job_id` idempotency로 중복 실행을 막고, 재시도는 새 `attempt` 식별자를 가진 별도 실행으로 기록한다.
- 현재 구현은 큐에 들어갔지만 시작하지 않은 작업만 `cancel()`할 수 있다. 실행 중인 외부 도구를 강제로 끊는 것은 Stage 4의 adapter별 계약으로 미룬다.
- 오류는 `tool_exit`, `artifact_missing`, `parse_invalid`, `timeout`, `resource_unavailable`처럼 분류한다. 임의 문자열만으로 운영 판단하지 않는다.

## 다음 검증

1. synthetic adapter가 의도적으로 비정상 종료하는 경우 `FAILED`와 오류 분류가 남는지 확인한다.
2. 잘못된 report가 생성되면 파싱 실패와 설계 check 실패를 구분한다.
3. 같은 요청을 여러 번 제출해도 하나의 run만 생성되는지 확인한다.
4. worker 수를 1로 제한하고 대기 중인 작업을 취소해 `CANCELLED`가 남는지 확인한다.
5. Stage 3 전까지는 retry/backoff, 이벤트 스트림, metrics endpoint를 추가하지 않는다. 먼저 상태 전이와 오류 의미를 고정한다.

## 현실적인 한계

인프로세스 `ThreadPoolExecutor`와 SQLite는 학습용 수직 슬라이스에 적합하지만, 여러 서버·내구성 큐·실제 라이선스 풀을 보장하지 않는다. 실제 Trace32/Aardvark도 장치 독점과 cleanup을 포함한 별도 자원 관리자 없이는 병렬 100명 규모를 주장할 수 없다.
