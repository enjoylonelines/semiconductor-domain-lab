# OpenSTA(정적 타이밍 분석 도구) client retry(호출자 재시도) evidence(근거)

실행일: 2026-09-25  
실행 revision(리비전): `c5b6b5f` + uncommitted client retry(호출자 재시도) changes(변경)  
원시 결과: [2026-09-25-opensta-client-retry.json](2026-09-25-opensta-client-retry.json)

## 질문과 방법

8개가 실행 중인 single-host OpenSTA profile(단일 호스트 OpenSTA 프로파일)에서 HTTP(하이퍼텍스트 전송 프로토콜) client(호출자)가 `429`를 받은 뒤 같은 `job_id`로 server hint(서버 힌트)만큼 기다려 재제출하면, 새 queue(대기열)를 만들지 않고 성공하는가를 확인한다.

실제 OpenSTA child process(하위 프로세스) 8개를 barrier(장벽)로 시작한 뒤 `RetryingJobClient`로 9번째 작업을 제출했다. client(호출자)는 jitter(무작위 지연) 없이 `retry_after_ms`를 정확히 한 번 기다렸다. 이후 결과와 모든 작업 상태를 확인했다.

## 결과

| 항목 | 결과 |
| --- | --- |
| profile(프로파일) | `max_workers=8`, `max_in_flight=8`, `resource_slots=8` |
| server hint(서버 힌트) | 300ms |
| client delay(호출자 대기) | 300ms, 1회 |
| fill jobs(기존 8개 작업) | 모두 `SUCCEEDED` |
| retried job(재시도 작업) | 같은 `job_id`로 `SUCCEEDED` |

## 결정과 한계

이 profile(프로파일)에서는 server-side automatic retry(서버 측 자동 재시도)나 persistent queue(영속 대기열) 없이 caller-side bounded retry(호출자 측 제한 재시도)를 채택한다. `RetryingJobClient`의 기본 최대 재시도는 3회이며, 실제 호출자는 random jitter(무작위 지연)를 기본 100ms까지 더한다.

이 근거는 한 client(호출자), 한 번의 429, fixed tiny workload(고정된 작은 작업부하)만 다룬다. same job ID with changed spec(변경된 명세로 같은 작업 식별자)은 별도 service/HTTP contract test(서비스/HTTP 계약 테스트)에서 `409`로 닫았다. 다수 호출자의 동시 재시도, heterogeneous arrival rate(서로 다른 도착률), persistent queue(영속 대기열)는 아직 열린 루프다.
