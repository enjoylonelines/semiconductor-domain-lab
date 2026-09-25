# OpenSTA(정적 타이밍 분석 도구) service budget(서비스 예산) evidence(근거)

실행일: 2026-09-25  
실행 revision(리비전): `4eb4650` + uncommitted service-budget harness(서비스 예산 도구)  
원시 결과: [2026-09-25-opensta-service-budget.json](2026-09-25-opensta-service-budget.json)

## 질문

직접 subprocess capacity(하위 프로세스 용량) 측정에서 선택한 single-host profile(단일 호스트 프로파일) `max_workers=8`, `max_in_flight=8`, `resource_slots=8`이 `JobService` 경계에서도 다음을 지키는가?

1. 8개까지는 실제 OpenSTA(정적 타이밍 분석 도구) child process(하위 프로세스)를 실행한다.
2. 9번째 요청은 Run(작업)을 만들거나 memory queue(메모리 대기열)에 쌓지 않고 backpressure(역압) 오류로 거절한다.
3. 성공한 작업이 자원을 반납한 뒤 다음 요청을 받을 수 있다.

## 방법과 결과

고정 tiny OpenSTA fixture(작은 OpenSTA 고정 입력)를 사용했다. 첫 8개 adapter call(어댑터 호출)은 barrier(장벽)에서 모아 child process(하위 프로세스) 시작을 겹치게 했다. 9번째 submit(제출)은 앞선 8개가 완료되기 전에 호출했다.

| 관측 | 결과 |
| --- | --- |
| profile(프로파일) | `max_workers=8`, `max_in_flight=8`, `resource_slots=8` |
| first batch(첫 배치) | 8개 모두 `SUCCEEDED` |
| controlled overlap(통제된 동시 실행) | true; 8개 child process(하위 프로세스)가 첫 완료 전 시작 |
| ninth submit(9번째 제출) | `BackpressureError: in-flight execution budget exhausted: 8` |
| rejected Run(거절된 작업) | `stored_run: null`; DB(데이터베이스)에 만들지 않음 |
| post-release submit(반납 뒤 제출) | `SUCCEEDED` |

## 채택과 한계

이 환경에서는 bounded rejection(제한된 거절)을 backpressure policy(역압 정책)로 채택한다. 즉 9번째 요청을 무한 대기열에 넣지 않고 호출자에게 즉시 재시도 가능 신호를 준다. 이는 user-facing retry delay(사용자 대상 재시도 지연), fairness(공정성), priority queue(우선순위 대기열), persistent queue(영속 대기열)를 구현하거나 평가한 결과가 아니다.

이번 증거는 fixed tiny workload(고정된 작은 작업부하), one host(한 호스트), no license limit observation(라이선스 한도 미관측)만 다룬다. 긴 작업·mixed normal/tight workload(정상/엄격 혼합 작업부하)·지속 도착률·취소/timeout(취소/시간 초과)과 동시에 발생하는 recovery(복구)는 다음 load/recovery cycle(부하/복구 사이클)에서 별도로 측정해야 한다.
