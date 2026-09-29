# Phase 5 Heavy workload(고부하 작업부하) Supervisor smoke(감독 실행 스모크) evidence(근거)

Date(날짜): 2026-09-29

## Purpose(목적)

기존 workload-calibration(작업부하 보정)의 PicoRV32 ×64 Heavy workload(고부하 작업부하)를 supervised execution(감독 실행) 경로에 연결해, 실제 OpenSTA result(결과)가 Run/Attempt(작업/실행 시도) 계약과 trusted result(신뢰 결과) 검증을 통과하는지 확인했다.

## Environment(환경)

- Docker Linux VM(도커 리눅스 가상 머신): 2 CPU, `2,053,644,288` bytes memory(메모리), 약 1.91 GiB.
- Heavy netlist(고부하 넷리스트): PicoRV32 ×64, 기존 calibration(보정)에서 peak RSS(최대 상주 메모리) 약 1.28 GiB.
- Host A Worker(호스트 A 워커)와 Supervisor A(감독자 A), PostgreSQL(포스트그레스큐엘)로 구성했다.
- Heavy netlist는 repository(저장소)에 vendoring(벤더링)하지 않고, Docker 공유가 가능한 로컬 경로의 read-only bind mount(읽기 전용 바인드 마운트)로만 제공했다.

## Observations(관측)

1. 기본 Supervisor memory limit(감독자 메모리 제한) `384 MiB`에서는 child process(하위 프로세스)가 `SIGKILL`되어 `PROCESS_EXITED=-9`이 기록됐다. Docker runtime(도커 런타임)은 `OOMKilled=true`를 보고했다. Run은 성공으로 추정되지 않고 `FAILED/INVALID`로 끝났다.
2. Supervisor limit(감독자 제한)을 test-only(테스트 전용)로 `1,500 MiB`로 올리자, 동일 Heavy workload가 `PROCESS_EXITED=0`, Attempt=`SUCCEEDED`, Run=`SUCCEEDED`, trust=`TRUSTED`로 끝났다.
3. Heavy report(고부하 보고서)는 기존 single-path parser contract(단일 경로 파서 계약)에 맞추어 completion marker(완료 표식), time unit(시간 단위), one reported path(하나의 보고 경로)를 출력하도록 보정했다. OpenSTA exit `0`만으로 신뢰 결과를 승인하지 않았고 parser/semantic validation(파서/의미 검증)까지 통과한 경우에만 `TRUSTED`가 됐다.

## Decision boundary(결정 경계)

이 Docker VM은 총 memory(메모리)가 약 1.91 GiB이므로, Heavy ×64 two-worker(두 워커)는 calibration peak RSS(보정 최대 상주 메모리)만 보아도 재현 가능한 실험 예산 밖이다. 따라서 이 환경에서 `1/2/4/8` scaling curve(확장 곡선)를 만들거나 Kafka trigger(카프카 조건)를 판단하지 않는다.

다음 Phase 5 matrix(단계 5 행렬)는 최소 2 Heavy workload(고부하 작업부하)를 동시에 수용할 memory budget(메모리 예산), CPU saturation(중앙 처리 장치 포화) 관측, PostgreSQL coordination(포스트그레스큐엘 조정) 측정을 갖춘 별도 환경에서만 시작한다. 현재 결과는 **one-worker supervised Heavy compatibility(단일 워커 감독 고부하 호환성)** 과 resource admission boundary(자원 허용 경계)만 지지한다.
