# Local connection lifecycle(로컬 연결 수명주기) closure(종결)

## Problem(문제) and scope(범위)

`Store`가 SQLite(라이트급 SQL 저장소) connection(연결)을 소유하지만 명시적으로 닫지 않았다. Python 3.14의 전체 test suite(테스트 모음)는 통과하면서도 `ResourceWarning: unclosed database`를 출력했다. 이는 execution correctness(실행 정확성), recovery(복구), 또는 multi-host(다중 호스트) durability(내구성)를 부정하는 결과는 아니지만, local single-host(로컬 단일 호스트) service(서비스)의 resource ownership(자원 소유권)이 닫히지 않았다는 결함이다.

이 cycle(사이클)은 SQLite connection lifecycle(연결 수명주기)만 다룬다. PostgreSQL(포스트그레SQL) operating candidate(운영 후보), multi-host(다중 호스트) workload(작업부하), durable queue(영속 대기열), deployment(배포)에는 결론을 내리지 않는다.

## Human hypothesis(사람 가설), prediction(예측), falsification condition(반증 조건)

- Human hypothesis(사람 가설): `unrecorded`; 사용자는 local reliability(로컬 신뢰성)를 먼저 닫는 작업을 지시했다.
- Prediction(예측): `Store.close()`와 `JobService.close()`가 executor(실행자)를 먼저 종료하고 connection(연결)을 닫으면, 동일 전체 suite(테스트 모음)는 `ResourceWarning`을 error(오류)로 승격해도 통과한다.
- Falsification condition(반증 조건): 같은 suite(테스트 모음)에서 `ResourceWarning`이 발생하거나, 종료 중인 job(작업)이 DB close(데이터베이스 종료) 이후 접근해 실패하거나, 종료 뒤 SQLite access(접근)가 성공한다.

## Smallest reinforcement(최소 보강)

- `Store.close()`는 idempotent(멱등)하게 단일 SQLite connection(연결)을 닫는다. context manager(컨텍스트 관리자)와 finalizer(최후 정리기)는 짧은 local caller(로컬 호출자)의 누락을 방어하지만, 운영 경로의 소유권은 명시적 `close()`다.
- `JobService.close()`는 먼저 `ThreadPoolExecutor.shutdown(wait=True)`로 제출된 local work(로컬 작업)를 끝낸 뒤 `Store.close()`를 호출한다. 따라서 in-flight work(진행 중 작업)가 닫힌 DB에 기록하지 않는다.
- API test(응용 프로그램 인터페이스 테스트)는 server shutdown(서버 종료) 뒤 현재 service(서비스)와 교체 전 service(서비스)를 닫는다.

## Experiment(실험) and evidence(근거)

| Run(실행) | Result(결과) |
| --- | --- |
| Baseline(기준선): `PYTHONPATH=src uv run python -W default -m unittest discover -s tests -v` | 57 tests(테스트) passed(통과), 14+ `unclosed database` `ResourceWarning` observed(관측) |
| Reinforced(보강 후): `PYTHONPATH=src uv run python -W error::ResourceWarning -m unittest discover -s tests -v` | 59 tests(테스트) passed(통과) in 3.363s; no `ResourceWarning` output(출력 없음) |
| Focused lifecycle contract(집중 수명주기 계약) | `Store.close()` is idempotent(멱등) and subsequent DB access(접근)는 `sqlite3.ProgrammingError`; `JobService.close()` waits for submitted work(제출된 작업) then makes DB access(접근) fail |

The original warning count is lower-bounded because Python can collect connections at different points; it is not a production leak rate(운영 누수율).

## Test Scope Review(테스트 범위 검토)

unit(단위): idempotent Store close(멱등 Store 종료)와 close 이후 access(접근)를 검사했다. integration(통합): API server(응용 프로그램 인터페이스 서버) test teardown(테스트 종료)가 worker(작업자) executor와 store(저장소)를 순서대로 닫는다. regression(회귀): 전체 59-test suite(테스트 모음)를 `ResourceWarning` error(오류) 조건으로 실행했다. fault-injection(장애 주입), contract(계약): 기존 OpenSTA timeout/cancel(시간 초과/취소), lease/reconciliation(임대/조정), backpressure(역압) 계약도 같은 suite(테스트 모음)에 포함됐다.

This cycle(사이클)은 recorded Red(실패) → Green(통과) evidence(근거)를 별도로 남기지 못했다. 새 lifecycle test(수명주기 테스트)는 구현과 함께 추가되었으므로, 이 결과를 TDD Red-Green-Refactor(TDD 실패-통과-리팩터) proof(증명)로 표현하지 않는다.

## Human Decision Gate(사람 결정 관문) and stop condition(중단 조건)

- Proposed changed belief(제안된 갱신): local SQLite path(로컬 SQLite 경로)는 명시적 service shutdown(서비스 종료) 시 in-flight local work(진행 중 로컬 작업)를 완료한 뒤 connection(연결)을 해제한다.
- Human decision(사람 결정): pending(대기). 이 보강을 local profile(로컬 프로파일)의 채택 근거로 기록할지는 사용자가 결정한다.
- Stop condition(중단 조건): warning-free(경고 없는) full suite(전체 테스트 모음)와 lifecycle contract(수명주기 계약)가 충족됐다. 다음 작업은 이 결론을 확장하지 않고, 별도 operational profile(운영 프로파일) decision gate(결정 관문)에서 multi-process(다중 프로세스)·PostgreSQL(포스트그레SQL)·restart(재시작)를 검증한다.

Project repository(프로젝트 저장소)가 source of truth(원본 기준)다. Career OS(커리어 OS)는 이 문서의 link(링크), revision(리비전), scope(범위), limitation(한계)만 요약할 수 있으며 raw evidence(원시 근거)를 복제하지 않는다.
