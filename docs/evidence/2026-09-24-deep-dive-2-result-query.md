# Deep Dive 2: result query(결과 조회) evidence(근거)

작성일: 2026-09-24

## Bounded question(제한된 질문)

Can revision comparison(설계 버전 비교) refuse condition-changed(조건 변경) data and still identify a new timing violation(새 타이밍 위반) when the same startpoint/endpoint(시작점/종점) appears in another corner(코너)?

The selected representative query(대표 조회)는 Q2 new violation(새 위반) comparison(비교)이다. It is a small SQLite(라이트급 SQL 저장소) correctness slice(정확성 슬라이스), not a production performance(운영 성능) claim.

## Red(실패) → Green(통과)

The new query contract(조회 계약) initially failed because `Store` had no revision(설계 버전), finding(발견 항목), comparability(비교 가능성), or index challenger(인덱스 도전 대안) APIs(응용 프로그래밍 인터페이스).

The implemented model(구현 모델) stores Revision(설계 버전) provenance(출처 추적) for design, Liberty hash(라이브러리 해시), SDC hash(설계 제약 해시), tool version(도구 버전), and parser version(파서 버전). Finding identity(발견 항목 식별)는 `startpoint + endpoint + path group + analysis type + corner`다.

The regression query(회귀 조회) returns `COMPARABLE` only when the design and all required comparison provenance(비교 출처 추적) match. Different Liberty/SDC(라이브러리/설계 제약)는 `CONDITION_CHANGED`; different tool/parser(도구/파서)는 `TOOL_CHANGED`; a different design(설계)은 `INCOMPARABLE`이다. None is silently treated as unchanged(변화 없음).

The sole challenger(유일 도전 대안)는 the composite finding index(복합 발견 항목 인덱스) `idx_findings_revision_identity`다. It is created explicitly, never by schema initialization(스키마 초기화), so a before/after(변경 전/후) benchmark(벤치마크) can choose it only after a measured trigger(측정된 조건).

## Verification(검증)

```text
PYTHONPATH=src .venv/bin/python -m unittest tests/test_result_query.py -v
```

Result(결과): 3 tests(테스트) passed(통과). They prove a different corner(다른 코너) remains a new violation(새 위반), condition change(조건 변경) withholds comparison(비교 보류), and index creation(인덱스 생성) is opt-in(명시 선택).

```text
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Result(결과): 38 tests(테스트) passed(통과) in `0.563s`. Existing SQLite connection `ResourceWarning` messages remained; no connection-lifecycle change(연결 수명주기 변경) was included.

## Limits(한계) and stop(종료)

No synthetic volume benchmark(합성 규모 벤치마크), SQLite query-plan capture(라이트급 SQL 저장소 조회 계획 수집), PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)`, materialization(사전 계산), partitioning(파티셔닝), or production migration(운영 마이그레이션) was run. The index is not adopted on a performance claim. This ends after one data model(데이터 모델) and one unopened challenger(열지 않은 도전 대안).
