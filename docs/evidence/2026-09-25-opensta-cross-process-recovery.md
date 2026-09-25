# Cross-process worker-loss recovery(교차 프로세스 작업자 손실 복구) 근거

작성일: 2026-09-25

## Question(질문)

worker process(작업자 프로세스)를 `SIGKILL`로 종료한 뒤 실제 OpenSTA(정적 타이밍 분석 도구) child process(하위 프로세스)가 계속 실행되면, reconciliation(상태 재조정)이 Run(작업)을 즉시 실패 처리해 같은 작업을 중복 실행하는가?

## Baseline(기준선)

보강 전 동일 harness(실험 도구)는 살아 있는 child process(하위 프로세스)에도 `recovered=["cross-process-worker-loss"]`, `ABANDONED/FAILED`를 기록했다. 따라서 실제 계산이 진행 중인데도 재시도 후보가 되는 safety failure(안전성 실패)를 재현했다.

## Reinforcement(보강)과 실행

Attempt(실행 시도)가 adapter-observed process PID(어댑터 관측 프로세스 PID)와 시작 시각을 durable SQLite(지속 라이트급 SQL 저장소)에 기록한다. single-host reconciliation(단일 호스트 상태 재조정)은 expired lease(만료 임대)라도 PID가 살아 있으면 terminal transition(종단 전이)을 하지 않고 `RUNNING`을 유지한다.

실행 명령:

```text
PYTHONPATH=src .venv/bin/python tools/opensta_cross_process_recovery_benchmark.py
```

고정 조건은 delayed Tcl(지연 Tcl) `after 1000`, 실제 OpenSTA child process(실제 OpenSTA 하위 프로세스), SQLite database(라이트급 SQL 데이터베이스), worker parent(작업자 부모) `SIGKILL`, `lease_seconds=0.05`다. 원시 결과는 [JSON](2026-09-25-opensta-cross-process-recovery.json)에 있다.

첫 번째 reconciliation(상태 재조정)에서는 child가 살아 있었고 `skipped_live_child`에 작업이 남았으며 Run/Attempt(작업/실행 시도)는 모두 `RUNNING`이었다. child 종료를 확인한 뒤 두 번째 reconciliation(상태 재조정)은 같은 작업을 `ABANDONED/FAILED`로 끝냈다. 이 결과는 성공을 추측하거나 live child(실행 중 하위 프로세스)를 재시도하지 않는다는 단일 호스트 안전 계약을 지지한다.

## Limits(한계)와 revalidation trigger(재검증 조건)

PID liveness(프로세스 식별자 생존 확인)는 PID reuse(프로세스 식별자 재사용)를 구별하지 못한다. 재사용이 발생하면 이 구현은 false terminal transition(잘못된 종단 전이) 대신 `RUNNING`을 더 오래 남기는 fail-safe(실패 안전) 방향이다. multi-host(다중 호스트), container restart(컨테이너 재시작), host reboot(호스트 재부팅), orphan process(고아 프로세스) 정리와 kill authority(종료 권한)는 검증하지 않았다.

이 중 하나가 실제 환경에서 필요해지면 process identity(프로세스 식별성), host identity(호스트 식별성), external supervisor(외부 감독자) 또는 durable queue(지속 대기열)를 challenger(도전 대안)로 비교한다. 이 근거만으로 분산 복구·용량·Kafka(카프카) 채택을 주장하지 않는다.
