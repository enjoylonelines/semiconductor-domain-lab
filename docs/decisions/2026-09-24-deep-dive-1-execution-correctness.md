# Deep Dive 1: execution correctness(실행 정확성) decision(결정)

작성일: 2026-09-24
상태: Human Decision Gate(사람 결정 관문) 대기

## Implemented bounded decision(구현된 제한 결정)

The repository now uses a fixed-input `OpenStaSubprocessAdapter` for the supported normal setup/max(정상 최대 지연) fixture. The adapter captures the direct child process(직접 하위 프로세스) exit code(종료 코드), stdout/stderr(표준 출력/표준 오류), and report artifact(보고서 산출물). A confirmed timeout(확인된 시간 초과) terminates the direct child and, after retry exhaustion(재시도 소진), records `TIMED_OUT` and untrusted result(신뢰 불가 결과).

This is a narrow execution-boundary reinforcement(실행 경계 보강). It does not adopt a queue(대기열), broker(브로커), distributed lease(분산 임대), Redis(레디스), PostgreSQL(포스트그레스큐엘), or Kafka(카프카).

## Human Decision Gate(사람 결정 관문)

The user still owns these policy decisions(정책 결정):

1. Whether an orphaned Attempt(고아 실행 시도) should receive automatic retry(자동 재시도) or require explicit resubmission(명시 재제출).
2. Whether measured child-process residue(하위 프로세스 잔존) or restart ownership ambiguity(재시작 소유권 모호성) is sufficient to open the lease/fence challenger(임대/차단 도전 대안).
3. Whether a measured concurrency limit(동시성 한계) warrants a bounded queue(제한 대기열) or any other resource-control change(자원 제어 변경).

## Prediction(예측), falsification(반증), stop condition(종료 조건)

The previously recorded Human prediction(사람 예측) remains unrecorded(기록되지 않음). The implemented challenger prediction(도전 대안 예측) was: a real delayed OpenSTA child process(실제 지연 OpenSTA 하위 프로세스) can be terminated within the adapter lifecycle(어댑터 수명주기), and its attempt(실행 시도) cannot be promoted to success(성공) after timeout(시간 초과). The focused integration/fault-injection tests(통합/장애 주입 테스트) supported that prediction in one fixed workload(고정 작업부하).

Stop(종료): do not broaden this slice automatically. The remaining lease(임대), heartbeat(심장박동), recovery(복구), and load(부하) questions require their own measured trigger(측정된 조건) and a Human Decision(사람 결정). The repository remains the source of truth(원본 기준); Career OS(커리어 운영체제) may only link to this decision and its evidence(근거).
