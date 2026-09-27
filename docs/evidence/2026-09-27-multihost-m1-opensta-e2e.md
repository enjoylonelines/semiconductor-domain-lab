# Multi-host M1(다중 호스트 M1) OpenSTA E2E(종단 간) baseline(기준선) evidence(근거)

Date(날짜): 2026-09-27

## Scope(범위)

이 검증은 single-machine multi-node simulation(단일 머신 다중 노드 모의)에서 two Host Agent(두 호스트 에이전트)가 shared PostgreSQL(공유 PostgreSQL)을 통해 `QUEUED` Run(대기 작업)을 claim(선점)하고, Linux ARM OpenSTA(리눅스 ARM OpenSTA)를 실행해 trusted completion(신뢰된 완료)을 기록할 수 있는지 확인한다.

이는 physical multi-host(물리 다중 호스트) 검증이 아니다. 두 Agent는 같은 Mac의 Docker Linux VM(리눅스 가상 머신) 안에서 서로 다른 container(컨테이너), PID namespace(PID 이름공간), artifact volume(산출물 볼륨), PostgreSQL connection(포스트그레스큐엘 연결)으로 분리됐다.

## Tool image(도구 이미지) and execution contract(실행 계약)

- base image(기반 이미지): `ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3`, observed(관측): `linux/arm64`.
- OpenSTA(정적 타이밍 분석 도구): `396536743ff33852cd8af176988f077219bc8b8d`; 기존 real STA evidence(실제 STA 근거)의 manifest(명세)와 같은 revision(리비전)이다.
- CUDD(결정 다이어그램 라이브러리): OpenSTA 공식 Ubuntu Dockerfile(도커파일)이 참조하는 3.0.0 tarball(타볼)을 SHA-256 `b8e966b4562c96a03e7fbea239729587d7b395d53cadcc39a7203b49cf7eeb69`로 확인해 빌드했다.
- fixture(픽스처): 기존 `tiny_mapped.v`, `normal.sdc`, `run.tcl`, OpenSTA source(소스)의 `sky130hd_tt.lib.gz`.
- artifact contract(산출물 계약): Adapter(어댑터)는 Agent별 `/artifacts` volume(볼륨) 아래에 job-specific directory(작업별 디렉터리)를 만들고 `timing.report`와 `stderr.log`를 기록한다. DB에는 이 경로와 process exit code(프로세스 종료 코드)를 provenance(출처 추적)로 남긴다.

## Commands and observed results(명령과 관측 결과)

```text
docker-compose -f compose.multihost.yml build host-agent-a
docker-compose -f compose.multihost.yml build host-agent-b
docker-compose -f compose.multihost.yml up -d
```

첫 Run(작업) `m1-real-opensta-normal`은 Agent A(에이전트 A)가 claim(선점)했다.

```text
m1-real-opensta-normal | SUCCEEDED | TRUSTED | m1-agent-a |
  /artifacts/eda-opensta-m1-real-opensta-normal-.../timing.report |
  /opt/opensta/build/sta | exit=0
```

Agent A를 stop(중지)한 뒤 새 Run(작업) `m1-real-opensta-agent-b-v2`를 제출했다. Agent B(에이전트 B)가 같은 workload(작업부하)를 완료했다.

```text
m1-real-opensta-agent-b-v2 | SUCCEEDED | TRUSTED | m1-agent-b |
  /artifacts/eda-opensta-m1-real-opensta-agent-b-v2-.../timing.report |
  /opt/opensta/build/sta | exit=0

worst slack max 9.459949
EDA_LAB_REPORT_END
```

관측 시 container constraint(컨테이너 제약)는 Agent A/B 각각 0.60 vCPU, 512 MiB, PID 64, read-only root filesystem(읽기 전용 루트 파일 시스템)이었다. PostgreSQL(포스트그레스큐엘)은 0.50 vCPU, 384 MiB였다.

## Supported claim(뒷받침하는 주장) and limit(한계)

이 근거는 Linux ARM tool image(리눅스 ARM 도구 이미지)에서 two independently started Host Agent(독립 시작 호스트 에이전트 둘)가 shared PostgreSQL(공유 PostgreSQL) 상태를 claim(선점)하고, real OpenSTA fixture(실제 OpenSTA 픽스처)를 실행해 artifact(산출물), parser validation(파서 검증), observed exit code(관측 종료 코드), execution owner(실행 소유자)를 함께 기록한다는 baseline(기준선)을 지지한다.

이 근거는 remote child recovery(원격 하위 프로세스 복구), Agent loss during live child(생존 하위 프로세스 중 에이전트 손실), artifact shared storage(산출물 공유 저장소), database restart(데이터베이스 재시작), network partition healing(네트워크 분할 복구), automatic retry(자동 재시도), physical-host failure(물리 호스트 장애), multi-host throughput(다중 호스트 처리량)을 지지하지 않는다. Agent A를 중지해 B의 **정상 실행 능력**을 분리 확인했을 뿐, A가 실행 중인 child(하위 프로세스)의 결과를 B가 회수했다고 주장하지 않는다.
