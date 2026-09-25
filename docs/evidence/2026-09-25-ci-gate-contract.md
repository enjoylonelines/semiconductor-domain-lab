# CI gate(지속적 통합 관문) 계약

작성일: 2026-09-25

`.github/workflows/ci.yml`의 `contract` job(계약 작업)은 모든 push(푸시)와 pull request(풀 리퀘스트)에서 `PYTHONPATH=src python -m unittest discover -s tests -v`를 실행한다. 여기에는 unit/regression/contract test(단위/회귀/계약 테스트), SQLite schema path(라이트급 SQL 스키마 경로), conditional terminal transition(조건부 종단 전이), provenance/trust(출처 추적/신뢰) 분리가 포함된다.

GitHub-hosted runner(깃허브 호스팅 실행기)에 기록된 `/tmp/eda-opensta-20260924` fixture(고정 입력)는 없다. `OpenStaSubprocessAdapterTests`는 그 경로가 없으면 skip(건너뜀)되며, workflow(작업흐름)는 이를 실제 도구 검증의 성공으로 해석하지 않는다. 로그에 `not run(미실행)` 이유를 남긴다.

실제 OpenSTA integration/fault-injection test(통합/장애 주입 테스트)는 `self-hosted`, `eda-opensta` label(레이블)을 가진 runner(실행기)에서 수동 `workflow_dispatch`로만 실행한다. 해당 runner(실행기)가 등록되기 전에는 이 작업은 pending(대기)이며 통과로 간주하지 않는다. Docker(도커), PostgreSQL(포스트그레스큐엘), Redis(레디스), Kafka(카프카) CI는 해당 구성 요소를 채택하지 않았으므로 추가하지 않는다.
