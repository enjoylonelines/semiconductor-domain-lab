# OpenSTA(정적 타이밍 분석 도구) mixed load/recovery(혼합 부하/복구) evidence(근거)

실행일: 2026-09-25  
실행 revision(리비전): `fd59d3d` + uncommitted load/recovery harness(부하/복구 도구)  
원시 결과: [2026-09-25-opensta-load-recovery.json](2026-09-25-opensta-load-recovery.json)

## 질문과 경계

선택한 single-host profile(단일 호스트 프로파일) `max_workers=8`, `max_in_flight=8`, `resource_slots=8`에서 failure classification(실패 분류), backpressure(역압), timeout release(시간 초과 반납), worker-loss reconciliation(작업자 손실 상태 재조정)이 결과를 성공으로 잘못 승격하지 않는가를 확인한다.

이것은 지속 arrival rate(도착률), 장시간 workload(작업부하), 실제 프로세스 강제 종료, multi-host recovery(다중 호스트 복구), production SLA(운영 서비스 수준 협약)의 측정이 아니다.

## 방법

첫 배치는 barrier(장벽)로 시작을 맞춘 8개 실제 OpenSTA child process(하위 프로세스)다.

- normal SDC(정상 설계 제약) 6개
- tight SDC(엄격 설계 제약) 1개
- `after 1000` Tcl(명령 언어)과 50ms deadline(마감 시각)을 사용한 confirmed timeout(확정 시간 초과) 1개

8개가 실행 중일 때 9번째 요청을 제출하고, 완료 뒤 post-timeout Run(시간 초과 뒤 작업)을 제출했다. 별도 service(서비스)에서 실제 OpenSTA child process(하위 프로세스)가 exit `0`으로 완료된 직후 terminal persistence(종단 저장) 전에 `SystemExit`를 주입했다. lease(임대)가 만료된 뒤 reconciliation(상태 재조정)을 한 번 실행했다.

## 결과

| 사례 | 관측 결과 |
| --- | --- |
| first batch(첫 배치) | 실제 child process(하위 프로세스) 8개 시작 |
| normal SDC(정상 설계 제약) 6개 | 모두 `SUCCEEDED`, `PASS`, `TRUSTED` |
| tight SDC(엄격 설계 제약) 1개 | `SUCCEEDED`, `FAIL`, `TRUSTED`; timing violation(타이밍 위반)을 실행 실패로 바꾸지 않음 |
| confirmed timeout(확정 시간 초과) 1개 | `TIMED_OUT`, `UNKNOWN`, `INVALID` |
| ninth submit(9번째 제출) | `in-flight execution budget exhausted: 8`; Run(작업) 미생성 |
| post-timeout Run(시간 초과 뒤 작업) | `SUCCEEDED`, `PASS`, `TRUSTED` |
| worker-loss injection(작업자 손실 주입) 전 | 실제 child 완료 뒤 Run/Attempt(작업/실행 시도) 모두 `RUNNING` |
| reconciliation(상태 재조정) 뒤 | Attempt(실행 시도) `ABANDONED`, Run(작업) `FAILED`; 성공으로 승격하지 않음 |

## 채택과 다음 조건

이 profile(프로파일)은 지금까지의 고정 workload(작업부하)에서 timeout(시간 초과)의 자원 반납과 post-artifact worker loss(산출물 뒤 작업자 손실)를 안전하게 보수적으로 처리했다. `ABANDONED/FAILED`는 실제 도구 결과가 존재했더라도 terminal persistence(종단 저장)를 확인하지 못한 상태를 성공으로 추측하지 않는 선택이다.

다음 cycle(사이클)은 fixed arrival schedule(고정 도착 일정)로 8개를 넘는 요청을 여러 wave(파동)로 보내 queue wait(대기열 대기), rejection ratio(거절 비율), p95 end-to-end latency(상위 95% 종단 간 지연), timeout/failure rate(시간 초과/실패율), recovery delay(복구 지연)를 측정하는 것이다. 그 결과가 없으면 persistent queue(영속 대기열), priority queue(우선순위 대기열), Kafka(카프카), multi-host(다중 호스트)를 열지 않는다.
