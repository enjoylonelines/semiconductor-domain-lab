# Stage 2 retry 검증

2026-09-23 Max workspace에서 테스트 4개 통과.

- `TimeoutError`와 `ConnectionError`만 retryable로 분류
- 최대 시도 횟수(`max_attempts`)를 넘으면 `FAILED`
- 각 시도는 `attempts` 테이블에 번호·상태·오류 종류·artifact 경로로 기록
- `parse_invalid`는 재시도하지 않음: 입력 형식 오류를 반복 실행해도 고쳐지지 않기 때문
- 동일 `job_id` 재제출은 기존 run을 반환해 중복 실행하지 않음

아직 지원하지 않는 범위:

- 프로세스 재시작 후 RUNNING 작업 복구
- 실행 중인 외부 프로세스 강제 취소
- 여러 서버 간 분산 queue
- 실제 Trace32/Aardvark 장비 자원 임대
