# Verification portfolio(검증 포트폴리오)

The directories express the primary proof each test supplies. A test can touch
more than one layer, but it is placed under the strongest claim it is intended
to support. `unittest discover -s tests` runs every directory in CI.

| directory(디렉터리) | proof type(검증 종류) | scope(범위) |
| --- | --- | --- |
| `unit/` | unit(단위) | parser(파서), adapter(어댑터), and client(클라이언트) rules without an external database or actual OpenSTA process |
| `integration/` | integration(통합) | API(응용 프로그래밍 인터페이스), PostgreSQL(포스트그레스큐엘), worker(작업자), and recorded OpenSTA path |
| `regression/` | regression(회귀) | established Stage 1(1단계) behavior retained across changes |
| `contract/` | contract(계약) | durable query/result identity(지속 조회/결과 식별성), lease fence(임대 차단), and HTTP(하이퍼텍스트 전송 프로토콜) response behavior |
| `fault_injection/` | fault-injection(장애 주입) | timeout(시간 초과), cancellation(취소), stale recovery(오래된 상태 복구), worker loss(작업자 손실), and completion boundary loss(완료 경계 손실) |

The fault-injection PostgreSQL/OpenSTA cases require both
`EDA_POSTGRES_TEST_DSN` for a disposable database and the recorded local
OpenSTA fixture. CI runs the portable suite; the actual-tool workflow is a
self-hosted verification gate. A skipped environment-dependent test is not
evidence that its invariant passed.
