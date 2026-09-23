# Fixture 시뮬레이션 보강

실제 Trace32/Aardvark 장비가 없어도 어댑터 경계의 운영 동작을 검증하기 위해 synthetic profile을 사용한다. 모든 결과에는 synthetic 출처를 표시하며 실제 장비 결과로 해석하지 않는다.

## 현재 profile

- `normal`: 정상 report와 timing metric 생성
- `missing_worst_slack`: 필수 metric 결측, parser `INVALID`
- `malformed_unit`: 지원하지 않는 단위, parser `INVALID`
- `timeout`: 실행 지연 후 timeout 예외
- `communication_error`: transport 예외

## 검증한 것

현재 unittest 3개가 통과한다.

- 정상 parser와 음수 slack 판정
- service end-to-end 및 동일 `job_id` idempotency
- 결측 report, timeout, 통신 오류 fixture

## 실제 장비와의 경계

이 시뮬레이션은 API·queue·worker·artifact·parser·DB·오류 상태를 검증한다. 전기적 신호, 보드 배선, 실제 디버거 명령, 장비 라이선스, 드라이버 동작은 검증하지 않는다. 실제 장비가 준비되면 같은 `HardwareAdapter` 계약 아래 real adapter smoke test를 추가한다.
