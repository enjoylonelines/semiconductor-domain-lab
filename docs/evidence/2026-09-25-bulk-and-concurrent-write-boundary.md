# Bulk ingest and concurrent write boundary(대량 적재 및 동시 쓰기 경계)

작성일: 2026-09-25

## Scope(범위)

이 보강은 Deep Dive 2(두 번째 딥다이브)의 핵심 성능 축을 새로 열지 않는다. execution correctness(실행 정확성)의 durable state(지속 상태)가 손상되지 않도록 하는 최소 data integrity(데이터 무결성) 경계만 닫는다.

## External basis(외부 근거)

SQLite(라이트급 SQL 저장소)는 foreign key constraint(외래 키 제약)를 연결별로 명시 활성화해야 하며 기본값에 의존하면 안 된다고 설명한다. [SQLite foreign key documentation](https://www.sqlite.org/foreignkeys.html)는 `PRAGMA foreign_keys=ON`을 각 connection(연결)에 적용하도록 명시한다. [SQLite transaction documentation](https://www.sqlite.org/lang_transaction.html)는 transaction(트랜잭션) 안의 write(쓰기)가 commit(커밋) 또는 rollback(되돌리기) 경계를 따른다고 설명한다.

## Reinforcement(보강)과 verification(검증)

- `Store`는 새 SQLite connection(라이트급 SQL 연결)마다 `PRAGMA foreign_keys=ON`을 설정한다. 존재하지 않는 revision(리비전)에 Finding(발견 항목)을 저장하려 하면 `IntegrityError`로 거절된다.
- `save_findings`는 `executemany` batch(대량 실행)가 실패하면 명시적으로 rollback(되돌리기)한다. 유효한 첫 행 뒤 `NOT NULL` 위반 행을 넣는 test(테스트)에서 예외 뒤 행 수는 0이었다.
- 같은 Attempt(실행 시도)를 보는 두 SQLite connection(라이트급 SQL 연결)이 동시에 terminal transition(종단 전이)을 시도하는 test(테스트)에서 owner token(소유자 토큰)만 성공하고 stale token(오래된 토큰)은 실패했다.

실행 명령:

```text
PYTHONPATH=src python3 -m unittest tests.test_result_query -v
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

결과는 focused test(집중 테스트) 6개와 전체 test(전체 테스트) 57개 통과다.

## Explicit limits(명시 한계)와 stop condition(종료 조건)

이 결과는 single-host SQLite(단일 호스트 라이트급 SQL 저장소), one batch(한 배치), one stale writer(한 오래된 작성자)를 다룬다. batch sizing(배치 크기), chunk retry(청크 재시도), idempotent ingest key(멱등 적재 키), long-running write contention(장시간 쓰기 경합), p95 ingest latency(상위 95% 적재 지연), multi-host writer(다중 호스트 작성자), queue(대기열)는 검증하지 않았다.

이 항목들은 현재 핵심축이 아니므로 여기서 멈춘다. 실제 workload(작업부하)에서 batch partial failure(배치 부분 실패), sustained lock error(지속 잠금 오류), ingest p95 growth(적재 상위 95% 지연 증가), duplicate ingest(중복 적재), replay/reprocessing(재생/재처리) 요구가 관측될 때만 별도 challenger(도전 대안)를 연다. Kafka(카프카)는 이 근거만으로 후보가 되지 않는다.
