# PostgreSQL operating-profile challenger(포스트그레스큐엘 운영 프로필 도전 대안) 근거

작성일: 2026-09-25

## Environment(환경)

동일 개발 호스트의 dedicated PostgreSQL 16 container(전용 포스트그레스큐엘 16 컨테이너)와 `psycopg` driver(드라이버)를 사용했다. 이는 multi-host deployment(다중 호스트 배포)가 아니라 client/server database contract(클라이언트/서버 데이터베이스 계약)의 최소 integration(통합) 검증이다.

실행 명령:

```text
EDA_POSTGRES_DSN='postgresql://…' PYTHONPATH=src uv run python tools/postgres_operating_profile_benchmark.py
```

## Result(결과)

| contract(계약) | result(결과) |
| --- | --- |
| duplicate Run claim(중복 작업 권한) | `created`, `existing`: Run(작업) 하나 |
| shared admission budget(공유 입장 예산) | duplicate Run(중복 작업) 1개와 unique Run(고유 작업) 7개만 생성; 나머지 9개는 backpressured(역압 거절) |
| two-worker terminal fence(두 작업자 종단 차단) | owner token(소유자 토큰) `true`, stale token(오래된 토큰) `false` |
| invalid bulk batch(무효 대량 배치) | `NotNullViolation`, post-failure finding count(실패 뒤 발견 항목 수) `0` |
| submit latency(제출 지연) | p50(중앙값) 약 2.7ms, p95(상위 95%) 약 5.6ms |

원시 결과는 [JSON](2026-09-25-postgres-operating-profile.json)에 있다. 기존 SQLite suite(라이트급 SQL 묶음)는 같은 revision(리비전)에서 57개 테스트를 통과했다.

## Decision(결정)

PostgreSQL challenger(포스트그레스큐엘 도전 대안)는 central database(중앙 데이터베이스)에서 필요한 최소 상태 계약을 만족했다. 그러나 이것은 actual OpenSTA multi-host workload(실제 OpenSTA 다중 호스트 작업부하), network fault(네트워크 장애), connection pool(연결 풀), migration compatibility(마이그레이션 호환성), backup/restore(백업/복원), HA/failover(고가용성/장애 조치), production capacity(운영 용량)를 검증하지 않는다.

따라서 현재 결정은 `PostgreSQL operational path candidate(포스트그레스큐엘 운영 경로 후보)`이며 채택은 Human Decision Gate(사람 결정 관문)에 남긴다. local validation(로컬 검증)은 SQLite(라이트급 SQL 저장소)를 계속 사용한다.
