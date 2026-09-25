# OpenSTA(정적 타이밍 분석 도구) fixed-arrival load(고정 도착 부하) evidence(근거)

실행일: 2026-09-25  
실행 revision(리비전): `202d42c` + uncommitted arrival harness(도착 도구)  
원시 결과: [2026-09-25-opensta-fixed-arrival.json](2026-09-25-opensta-fixed-arrival.json)

## 질문과 방법

selected profile(선택된 프로파일) `max_workers=8`, `max_in_flight=8`, `resource_slots=8`에서 capacity(용량)보다 하나 많은 요청이 반복될 때 queue growth(대기열 증가) 대신 bounded rejection(제한된 거절)이 일정하게 유지되는가를 측정한다.

고정 tiny OpenSTA workload(작은 OpenSTA 작업부하)에 대해 9개 요청을 즉시 제출하고 8개 완료를 기다리는 wave(파동)를 4회 반복했다. 각 wave(파동)의 8개 수락 작업은 barrier(장벽) 뒤 실제 child process(하위 프로세스) 시작을 겹치게 했다. p95 end-to-end latency(상위 95% 종단 간 지연)는 submit(제출)부터 service future(서비스 future) 완료까지 측정했다.

## 결과

| 항목 | 결과 |
| --- | ---: |
| 제출 | 36 |
| 수락·성공 | 32 |
| 즉시 거절 | 4 |
| rejection ratio(거절 비율) | 11.1% |
| 거절된 Run(작업)의 DB 저장 | 0 |
| p50 end-to-end latency(중앙값 종단 간 지연) | 268.384 ms |
| p95 end-to-end latency(상위 95% 종단 간 지연) | 273.885 ms |
| 최대 종단 간 지연 | 273.949 ms |
| controlled child overlap(통제된 하위 프로세스 동시 실행) | 4/4 wave(파동) true |

32개 수락 작업은 모두 `SUCCEEDED`였다. 각 wave(파동)에서 정확히 한 요청이 `BackpressureError`로 거절되고 Run(작업)을 만들지 않았으므로, 이 workload(작업부하)에서는 queue(대기열)가 쌓이거나 지연이 다음 wave(파동)에 누적되는 증거가 없었다.

## 결정과 한계

현재 profile(프로파일)은 persistent queue(영속 대기열) 없이 bounded rejection(제한된 거절)을 유지한다. 9번째 요청이 사라졌다는 의미가 아니라, 호출자가 명시적으로 다시 제출할 책임을 받는다는 뜻이다. 이 선택은 자원 예산을 넘는 작업을 메모리에 무기한 쌓지 않는다.

이 실험은 batch arrival(배치 도착) 4회만 다룬다. 실제 user retry behavior(사용자 재시도 행동), arrival rate(도착률), deadline(마감 시각), fairness(공정성), priority(우선순위), longer design(더 긴 설계), license pressure(라이선스 압박)는 아직 측정하지 않았다. 그 중 하나가 observed rejection pressure(관측된 거절 압박) 또는 p95 latency growth(상위 95% 지연 증가)로 나타날 때만 bounded persistent queue(제한된 영속 대기열)를 challenger(도전 대안)로 비교한다. Kafka(카프카)는 replay(재생)·다중 consumer(소비자)·보존·재처리·처리량 요구가 함께 관측될 때만 별도로 연다.
