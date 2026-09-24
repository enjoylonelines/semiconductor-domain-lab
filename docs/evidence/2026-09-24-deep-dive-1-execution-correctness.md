# Deep Dive 1: execution correctness(실행 정확성) evidence(근거)

작성일: 2026-09-24

## Question(질문) and boundary(경계)

Can the supported OpenSTA(정적 타이밍 분석 도구) setup/max(최대 지연) fixture run as an observed operating-system child process(운영체제 하위 프로세스), and can a confirmed timeout(확인된 시간 초과) avoid a false `SUCCEEDED` transition(성공 상태 전이)?

This is a single-worker(단일 작업자), fixed-fixture(고정 입력) cycle. It does not prove lease(임대), heartbeat(심장박동), multi-worker ownership(다중 작업자 소유권), cancellation escalation(취소 단계 상승), or capacity(용량).

## Baseline(기준선)

Before this slice, `SyntheticTimingAdapter` only created synthetic(합성) reports. The durable `RUNNING` recovery test could distinguish a still-live local future(로컬 future) from a stale record(오래된 기록), but it did not start or terminate an OpenSTA child process(하위 프로세스).

The fixed command template(명령 템플릿) is:

```text
<OpenSTA> -no_init -exit run.tcl
```

The adapter(어댑터) copies only `run.tcl`, `normal.sdc`, and `tiny_mapped.v` into an attempt-specific temporary work directory(작업 디렉터리), supplies `EDA_LIB` and `EDA_SDC` as explicit environment variables(환경 변수), captures stdout/stderr(표준 출력/표준 오류), and stores stdout as `timing.report`.

One measured normal run(정상 실행), on the local evidence environment(로컬 근거 환경), produced:

| field(필드) | observed value(관측값) |
| --- | --- |
| process exit(프로세스 종료) | `0` |
| elapsed seconds(경과 초) | `0.224301` |
| report SHA-256(보고서 SHA-256) | `05c825e5700e6414c9239010facb89acb159ed49849fb951061825584cd00c3e` |
| completion marker(완료 표식) | `EDA_LAB_REPORT_END` present(존재) |

This is one baseline observation(기준선 관측), not a latency(지연) or throughput(처리량) claim.

## Red(실패) → Green(통과)

The initial integration test(통합 테스트) imported `OpenStaSubprocessAdapter` before it existed. It failed with `ImportError`, establishing the missing execution boundary(실행 경계).

The reinforcement(보강) adds `OpenStaSubprocessAdapter` with a bounded `communicate(timeout=...)` lifecycle(수명주기). On timeout(시간 초과), it sends `SIGTERM`, waits for the configured grace period(유예 기간), uses `SIGKILL` only if needed, collects available output, and raises a `TimeoutError` that records the observed PID(프로세스 식별자) and termination signal(종료 신호).

A fault-injection test(장애 주입 테스트) prepends Tcl(명령 언어) `after 1000` to a copied fixture script(고정 입력 스크립트). The real OpenSTA child process(실제 OpenSTA 하위 프로세스) is therefore alive when the adapter's `0.05` second timeout(시간 초과) occurs. The test requires `termination=SIGTERM`.

The service(서비스) now records an exhausted confirmed timeout(확인된 시간 초과)을 `TIMED_OUT` and `trust_status(신뢰 상태)=INVALID`로 끝낸다. A retryable failure(재시도 가능 실패) remains a numbered Attempt(실행 시도); it never becomes `SUCCEEDED` without a later successful attempt.

## Verification(검증)

```text
PYTHONPATH=src .venv/bin/python -m unittest tests/test_async_lifecycle.py -v
```

Result(결과): 7 tests(테스트) passed(통과), including the normal OpenSTA integration test(정상 OpenSTA 통합 테스트), a real child timeout fault-injection test(실제 하위 프로세스 시간 초과 장애 주입 테스트), and the durable `TIMED_OUT` service transition(서비스 상태 전이).

```text
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Result(결과): 35 tests(테스트) passed(통과) in `0.564s`. Python emitted existing SQLite connection `ResourceWarning` messages during the bounded-batch test(제한 배치 테스트); this slice did not change connection ownership(연결 소유권), so the warnings remain a separate follow-up candidate(후속 후보).

`git diff --check` passed(통과).

## Test Scope Review(테스트 범위 검토)

| test type(테스트 종류) | coverage(범위) | result(결과) |
| --- | --- | --- |
| unit test(단위 테스트) | timeout(시간 초과) retry classification(재시도 분류), terminal state(종단 상태) | passed(통과) |
| integration test(통합 테스트) | actual OpenSTA child process(실제 OpenSTA 하위 프로세스), report collection(보고서 수집) | passed(통과) |
| regression test(회귀 테스트) | nonzero exit(0이 아닌 종료), parse/check/trust separation(파싱/검사/신뢰 분리) | passed(통과) |
| fault-injection test(장애 주입 테스트) | real OpenSTA Tcl delay(실제 OpenSTA Tcl 지연) then `SIGTERM` | passed(통과) |
| contract test(계약 테스트) | fixed command inputs(고정 명령 입력) and explicit artifact result(명시 산출물 결과) | covered by adapter lifecycle tests(어댑터 수명주기 테스트로 포괄) |

## Falsification(반증) and limits(한계)

The observation would falsify this reinforcement(보강) if the delayed OpenSTA child process(지연된 OpenSTA 하위 프로세스) remained live after the adapter returned, or if the timeout attempt(시간 초과 실행 시도) ended as `SUCCEEDED`. Neither occurred in this bounded test(제한된 테스트).

The adapter observes and terminates only its direct OpenSTA child process(직접 OpenSTA 하위 프로세스). It does not yet establish process-group cleanup(프로세스 그룹 정리), durable PID reuse protection(지속 PID 재사용 방지), restart-safe lease ownership(재시작 안전 임대 소유권), heartbeat-based reconciliation(심장박동 기반 조정), cancellation API(취소 API), 1/2/4/8 concurrency(동시성) measurement(측정), or a production tool/license environment(운영 도구/라이선스 환경). Kafka(카프카), Redis(레디스), and PostgreSQL(포스트그레스큐엘) were not introduced.
