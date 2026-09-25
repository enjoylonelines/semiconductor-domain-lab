# Deep Dive 2: result query(결과 조회) decision(결정)

작성일: 2026-09-24
상태: Human Decision Gate(사람 결정 관문) 대기

The bounded implementation(제한된 구현) adopts strong Finding identity(강한 발견 항목 식별) and fail-closed comparability(실패 안전 비교 가능성) for Q2 new violation comparison(새 위반 비교). The composite index challenger(복합 인덱스 도전 대안) reduced one identical synthetic workload(동일 합성 작업부하) from `1.361966s` to `0.002929s` while preserving identical ordered results(동일한 순서 결과). It remains explicit opt-in(명시 선택) rather than a general default(일반 기본값), because write/storage cost(쓰기/저장 비용) and a user-selected budget(사용자 선택 예산) are still unmeasured.

The delegated decision(위임된 결정)은 the composite index(복합 인덱스)를 Q2 new-violation query(새 위반 조회)에서만 explicit operational setting(명시 운영 설정)으로 유지한다. 기본 API(응용 프로그래밍 인터페이스) 조회는 storage policy(저장 정책)를 바꾸지 않으며, `enable_new_violation_index=True`로 시작한 서비스만 index(인덱스)를 준비한다. 동일 workload(동일 작업부하)에서 read benefit(조회 이득)은 크지만, ingest time(적재 시간) 약 45% 증가와 database size(데이터베이스 크기) 약 1.05 MiB 증가가 측정됐다. materialization(사전 계산)과 migration(마이그레이션)은 별도 한계 실험 전 도입하지 않는다. Career OS(커리어 운영체제) may only link to this repository decision(저장소 결정) and evidence(근거).
