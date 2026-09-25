# OpenSTA(정적 타이밍 분석 도구) single-host capacity(단일 호스트 용량) evidence(근거)

실행일: 2026-09-25  
실행 revision(리비전): `a44575c` + uncommitted capacity harness(용량 도구)  
원시 결과: [2026-09-25-opensta-single-host-capacity.json](2026-09-25-opensta-single-host-capacity.json)

## 질문과 경계

질문은 “현재 개발 host(호스트) 한 대에서 고정 OpenSTA(정적 타이밍 분석 도구) workload(작업부하)를 몇 개까지 동시에 실행해도 처리량 증가가 유지되는가”다. 이것은 deployment sizing(배포 규모 산정), server fleet(서버 군), license capacity(라이선스 용량), 큰 design(설계), 다른 co-tenant workload(공동 실행 작업부하)의 증거가 아니다.

| 항목 | 관측 또는 제한 |
| --- | --- |
| server count(서버 수) | 1 |
| host(호스트) | macOS arm64, physical/logical CPU(물리/논리 중앙 처리 장치) 10/10 |
| memory(메모리) | 64 GiB |
| repository disk free(저장소 가용 디스크) | 약 828 GiB |
| tool workload(도구 작업부하) | 고정 tiny netlist(작은 넷리스트) + Sky130 Liberty(셀 라이브러리) + normal SDC(정상 설계 제약) + OpenSTA 3.1.0 |
| concurrency(동시성) | 1, 2, 4, 8 |
| repeat(반복) | 각 5 batch(배치), 총 75 actual child process(실제 하위 프로세스) |
| guardrail(보호 한도) | 최대 8개 child process(하위 프로세스), child timeout(하위 프로세스 시간 초과) 2초 |

`tools/opensta_capacity_benchmark.py`는 barrier(장벽) 뒤 각 child process(하위 프로세스)의 PID(프로세스 식별자)·시작 시각을 수집했다. 20개 모든 batch(배치)에서 마지막 child process(하위 프로세스) 시작 시각이 첫 완료 시각보다 앞섰으므로, 단순 요청 제출 수가 아닌 controlled overlap(통제된 동시 실행)을 확인했다.

## 결과

| concurrency(동시성) | mean throughput(평균 처리량, runs/s) | p95 batch wall time(상위 95% 배치 경과 시간) | 1개 대비 처리량 |
| ---: | ---: | ---: | ---: |
| 1 | 4.162 | 243.657 ms | 1.00x |
| 2 | 8.332 | 247.522 ms | 2.00x |
| 4 | 15.968 | 252.747 ms | 3.84x |
| 8 | 28.994 | 281.836 ms | 6.97x |

모든 실행은 exit code(종료 코드) `0`과 1,707-byte report(보고서)를 만들었다. 8 동시성의 p95 batch wall time(상위 95% 배치 경과 시간)은 1 동시성보다 약 15.7% 증가했지만 처리량은 약 7배가 됐다. 이 범위에서는 saturation point(포화 지점)가 관측되지 않았다.

## 채택과 한계

현재 개발 host(호스트)의 fixed OpenSTA profile(고정 OpenSTA 프로파일)은 `max_workers=8`, `max_in_flight=8`, `resource_slots=8`로 명시할 수 있다. 이는 10개 CPU(중앙 처리 장치) 중 8개까지만 OpenSTA(정적 타이밍 분석 도구) child process(하위 프로세스)에 배정하는 bounded execution budget(제한 실행 예산)이다. `JobService`의 일반 기본값을 모든 환경에 맞지 않게 바꾸지는 않는다. 배포 환경은 호스트별 측정 결과를 가진 명시 설정만 사용한다.

다음 중 하나가 생기면 이 값은 재측정 전까지 채택하지 않는다: 다른 CPU/memory quota(중앙 처리 장치/메모리 할당량), 컨테이너 제한, 실제 license seat(라이선스 좌석) 수, larger netlist(더 큰 넷리스트), 다른 EDA tool(EDA 도구) 동시 실행, queue wait(대기열 대기)와 deadline(마감 시각) 요구, p95 latency(상위 95% 지연) 또는 timeout/failure rate(시간 초과/실패율) 악화.

9개 이상 동시성, multi-host(다중 호스트), autoscaling(자동 확장)은 이번 실험의 stop condition(종료 조건) 밖이다. 8이 배포 최적값이거나 회사 환경의 서버 제약이라는 주장은 하지 않는다.
