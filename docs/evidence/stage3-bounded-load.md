# Stage 3 초기 부하 검증

현재는 production capacity 시험이 아니라 bounded smoke test다.

- worker: 4개
- 제출 작업: 20개
- 작업당 synthetic 실행 시간: 5ms
- 저장소: 단일 SQLite 연결 + lock
- 결과: 20개 모두 `SUCCEEDED`, job_id 20개 모두 고유
- 테스트 전체: 5개 통과

이 수치로 100명 동시 사용자를 지원한다고 주장하지 않는다. 실제 부하 모델에는 작업 크기, report 크기, 동시 제출률, retry 비율, DB 디스크, queue 내구성, 장비·라이선스 독점이 포함되어야 한다. 다음 단계는 이 가정을 명시한 별도 측정 스크립트와 p95 대기시간·실패율 기록이다.
