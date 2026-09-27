# EDA execution environment profile(EDA 실행 환경 프로필) review(검토)

Date(날짜): 2026-09-27

## Sources(출처) and bounded inference(제한된 추론)

- [Wanted company profile](https://www.wanted.co.kr/company/30155), accessed 2026-09-27: Qualitas Semiconductor(퀄리타스반도체)를 high-speed interconnect solution(고속 인터커넥트 솔루션) 업체로 소개한다.
- [Careerly job repost](https://careerly.co.kr/job/17170651), accessed 2026-09-27: REST API(REST 응용 프로그램 인터페이스), asynchronous event system(비동기 이벤트 시스템), relational database(관계형 데이터베이스), Redis Pub/Sub(레디스 발행/구독), semiconductor file parsing(반도체 파일 파싱), container operation(컨테이너 운영), migration(마이그레이션), CI/CD(지속적 통합·지속적 배포)를 나열한다. 재게시 채용 공고이므로 현행 내부 아키텍처의 직접 증거는 아니다.
- [OpenSTA examples](https://opensta.readthedocs.io/en/latest/Examples/), accessed 2026-09-27: Liberty(라이브러리), Verilog(베릴로그), SDC(설계 제약), 선택적 SPEF(기생 성분) 입력을 분석해 timing report(타이밍 보고서)를 생성하는 흐름을 설명한다.

따라서 이 repository(저장소)는 consumer web traffic(소비자 웹 트래픽)이나 enterprise Kafka platform(기업용 카프카 플랫폼)을 모사하지 않는다. 다음 M1 profile(프로필)은 **소수 엔지니어의 input-bound, artifact-bearing execution(입력 의존·산출물 보유 실행)** 이라는 작업 가설을 검증하기 위한 것이다. 실제 회사의 실행 건수, host count(호스트 수), license server(라이선스 서버), SLA(서비스 수준 협약)는 이 출처로 확정하지 않는다.

## M1 single-machine multi-node simulation(단일 머신 다중 노드 모의)

Docker runtime(도커 실행 환경)이 현재 2 vCPU와 약 1.9 GiB memory(메모리)로 제한된 것을 확인했다. 다음 제약을 고정한다.

| component(구성 요소) | CPU | memory(메모리) | purpose(목적) |
| --- | ---: | ---: | --- |
| PostgreSQL(포스트그레스큐엘) | 0.50 vCPU | 384 MiB | authoritative Run/Attempt state(원본 작업/실행 시도 상태) |
| Host Agent A(호스트 에이전트 A) | 0.60 vCPU | 512 MiB | host-local session(호스트 로컬 세션), one execution slot(실행 슬롯 하나) |
| Host Agent B(호스트 에이전트 B) | 0.60 vCPU | 512 MiB | host-local session(호스트 로컬 세션), one execution slot(실행 슬롯 하나) |
| runtime headroom(실행 환경 여유) | 0.30 vCPU | 약 540 MiB | network/process overhead(네트워크/프로세스 오버헤드) |

Agent마다 `pids_limit=64`, read-only root filesystem(읽기 전용 루트 파일 시스템), `tmpfs` temporary workspace(임시 작업 공간), independent artifact volume(독립 산출물 볼륨)을 둔다. Agent들은 internal Docker network(내부 도커 네트워크)에서 PostgreSQL만 공유한다. host port(호스트 포트)는 노출하지 않는다.

OpenSTA(정적 타이밍 분석 도구) binary(바이너리)는 이 M1 container profile(컨테이너 프로필)에 아직 포함하지 않는다. 현재 probe(탐침)는 Agent registration(에이전트 등록), heartbeat(심장박동), session fencing(세션 차단), network isolation(네트워크 격리)만 검증한다. actual OpenSTA execution(실제 OpenSTA 실행)은 Linux-compatible tool image(리눅스 호환 도구 이미지), immutable input mount(불변 입력 마운트), artifact retrieval contract(산출물 회수 계약)를 준비한 뒤 별도 M1-E2E로 연다.

## M1 environment probe(환경 탐침) result(결과)

`docker-compose -f compose.multihost.yml up --build -d`로 PostgreSQL 16 container(포스트그레스큐엘 16 컨테이너)와 두 Host Agent container(호스트 에이전트 컨테이너)를 기동했다. PostgreSQL healthcheck(상태 확인) 뒤 Agent A/B가 각각 다른 session ID(세션 식별자)를 기록했다.

The environment(환경)은 `postgres:16-alpine@sha256:721873…6080ea`와 `python:3.12-slim@sha256:f77ac9…84e51f` image digest(이미지 다이제스트)로 고정했다.

| observation(관측) | observed result(관측 결과) |
| --- | --- |
| resource limits(자원 제한) | Agent A: 0.60 vCPU, 512 MiB, PID 64, read-only root filesystem(읽기 전용 루트 파일 시스템) |
| startup(시작) | PostgreSQL `healthy`; Agent A/B `Up`; 서로 다른 host/session ID(호스트/세션 식별자) 기록 |
| network fault(네트워크 장애) | Agent A를 internal network(내부 네트워크)에서 5초 분리하자 A session lease(세션 리스)는 expired(만료), B session lease는 active(활성) |
| restart(재시작) | Agent A 재연결·재시작 뒤 새 session ID(세션 식별자)를 등록해 이전 A session을 fence(차단) |

이 결과는 `docker network disconnect` 기반 agent-to-database connectivity loss(에이전트-데이터베이스 연결 손실)만 다룬다. database restart(데이터베이스 재시작), partition healing(분할 복구), actual OpenSTA child process(실제 OpenSTA 하위 프로세스), remote report collection(원격 보고서 회수), physical-host failure(물리 호스트 장애)는 아직 검증하지 않았다.
