# Heavy workload benchmark plan

## 목적
Cycle 1의 ownership/recovery 구현을 수정하지 않고 OpenSTA workload 크기를 먼저 검증한다. 이후 Cycle 1 종료 후에만 동일 Heavy workload를 worker scaling 및 SIGKILL recovery 실험에 연결한다.

질문: **현재 OpenSTA workload에서 worker 확장 효과가 둔화되는 한계는 어디이며, 동일 workload에 worker 장애를 주입해도 accepted job을 안전하게 종결할 수 있는가?**

## 격리
- base: `a078819e0c9d91276f43b21f86a617f02c980261`
- branch: `workload-calibration-cycle`
- Cycle 1: 별도 `multihost-validation-cycle`; 이 작업에서 제품/Cycle 1 코드는 수정하지 않는다.
- canonical portfolio/resume 수정 없음.

## 후보와 선택
| 후보 | 출처/라이선스 | 합성/OpenSTA | 판단 |
|---|---|---|---|
| OpenSTA GCD | OpenSTA upstream, 저장소 GPLv3; SKY130 fixture 포함 | 이미 SKY130 netlist/SDC 제공 | 1,292 cell reference지만 동일 report 조건 wall 0.21~0.22s로 Small과 분리되지 않아 Medium에서 제외 |
| PicoRV32 | YosysHQ/picorv32, ISC, pinned `ef203c2...` | 단일 Verilog를 Yosys 0.69로 SKY130 mapping 성공 | Medium 채택. 6,404 mapped cells |
| Ibex | lowRISC/ibex, Apache-2.0 | 공식 문서상 Yosys 직접 사용 제약, sv2v 전처리 경로 필요 | 이번 재현성/의존성 예산에서는 보류 |

Heavy는 별도 외부 IP를 추가하지 않고 PicoRV32 mapped module을 16개 인스턴스화한 **calibration-only wrapper**다. 이는 production/실무 규모를 뜻하지 않으며 timing graph와 메모리 사용량을 실제로 증가시키기 위한 통제된 부하 조절 장치다.

## workload 정의
- Small: 기존 tiny mapped fixture, 3 mapped cells. correctness/regression 기준.
- Medium: PicoRV32 1개, 6,404 mapped cells.
- Heavy: PicoRV32 16개 wrapper, effective 102,464 mapped cell instances.
- 이름은 cell 수만으로 정하지 않고 OpenSTA 유효 실행의 wall/RSS 분리가 확인된 뒤 확정한다.

## 측정 계약
OpenSTA 3.1.0 `396536743f...`, SKY130 TT Liberty SHA256 `70a45b...03ecf`, `-no_init -exit`.
각 workload 최소 5회. `/usr/bin/time -l`의 real/user/sys 및 maximum RSS와 stdout report bytes를 보존한다. median/p95를 분리한다. 첫 실행이 느리면 warm/cache 가능성을 기록하되 임의 제거하지 않는다.

현재 raw 임시 로그는 `/tmp/*cal*`, `/tmp/pico_valid_*`, `/tmp/picox16_*`에 있고, 재현 harness의 canonical raw 위치는 `benchmark/raw/`이다. `benchmark/run_opensta_workload_benchmark.py`가 동일 형식으로 raw stdout/stderr와 summary를 생성한다.

## 향후 scaling matrix
Cycle 1 종료 후 최종 HEAD를 병합/재기반한 뒤에만 실행한다.

- workload: Small / Medium / Heavy
- workers: 1 / 2 / 4 / 8
- job count: calibration 후 정한다. 100/1000을 선결정하지 않는다.
- performance: makespan, throughput, p50/p95 latency
- resource: CPU, peak memory, worker별 사용량
- correctness: accepted, terminal, success/fail, duplicate execution, invalid result commit, non-terminal
- scaling: 1→2, 2→4, 4→8 marginal throughput gain 및 makespan reduction

## 사전 scaling-limit 기준
결과를 본 뒤 임계값을 만들지 않는다. 아래 중 하나가 발생한 첫 worker 단계부터 **scaling-limit candidate**로 표시한다.

1. 직전 worker 단계 대비 throughput의 marginal improvement가 **15% 미만**.
2. worker 증가 후 p95 latency가 직전 단계보다 **10% 이상 악화**.
3. CPU가 실험 구간의 대부분에서 포화되어 worker 추가가 throughput으로 이어지지 않음.
4. memory pressure/swap 또는 OOM이 관찰됨.
5. DB coordination 대기나 OpenSTA 자원 경쟁이 병목 증거로 관찰됨.

15%/10%는 성능 성공 기준이 아니라 “추가 worker의 효용이 작아졌는지 재검토할 사전 trigger”다. 실제 원인은 resource evidence로 판정한다.

## Phase 5 gate
현재 실행 금지. Cycle 1 종료 후 Heavy의 baseline과 동일 workload + worker SIGKILL을 비교한다.
안전성은 terminal N/N, invalid result commit 0, duplicate execution 0으로 각각 보고한다. 성능은 baseline 대비 makespan 및 failure overhead로 별도 보고한다. 임의의 “N% 안전” 합성 지표를 만들지 않는다.

## 2026-09-29 supervised execution(감독 실행) integration(통합) result(결과)

Heavy ×64는 Supervisor(감독자) 경로에서 actual OpenSTA(실제 OpenSTA) `SUCCEEDED/TRUSTED`까지 확인했다. 이 실행에서 기본 384 MiB Supervisor limit(감독자 제한)은 OOM(메모리 부족)으로 종료됐고, test-only 2 GiB limit(테스트 전용 제한)에서 one-worker baseline(단일 워커 기준선)을 통과했다. 이 결과는 실행 및 recovery(복구) 경로의 관찰이며, 동시 실행 한계의 근거는 아니다.

이전 기록의 약 1.91 GiB Docker Linux VM(도커 리눅스 가상 머신) 설명은 당시 작은 VM 프로필에만 해당한다. 2026-09-30 calibration(보정)은 8 CPU, 19.49 GiB VM 프로필에서 별도로 수행됐다.

## 2026-09-30 SS Heavy memory admission(메모리 입장) correction(정정)

SS Heavy child(자식 프로세스) 하나를 1 CPU container(컨테이너)에서 세 번씩 실행한 결과, 1.000 GiB 및 1.125 GiB에서는 모두 OOM killed(메모리 부족 종료)됐고, 1.250 GiB는 3/3 valid(유효)였지만 최대 peak(최대 사용량) 대비 여유가 4.9%였다. 1.500 GiB는 3/3 valid, OOM 0/3, 최대 peak 대비 20.8% 여유를 보였다.

따라서 1.5 GiB는 이 고정 입력과 단일 child profile(자식 프로세스 프로필)의 admission candidate(입장 후보)로만 기록한다. 8 CPU VM에서 8 × 1.5 GiB = 12 GiB라는 예산 산술은 남은 약 7.49 GiB를 시스템 구성요소에 남기지만, 8개의 SS Heavy child가 동시에 안전하거나 더 빠르다는 검증은 아니다. 자세한 raw evidence(원시 근거)는 [SS Heavy memory admission calibration(SS Heavy 메모리 입장 보정)](../evidence/2026-09-30-ss-heavy-memory-admission.md)에 남긴다.

2026-09-30에는 이 admission candidate(입장 후보)를 SS Heavy 8개 동시 실행으로 세 번 확인했다. 24/24가 `SUCCEEDED/TRUSTED`, OOM 0/8, PostgreSQL lock wait(잠금 대기) 최대 0으로 종결됐고, Supervisor CPU는 각 1 CPU cap(제한)에 포화됐다. 자세한 raw evidence(원시 근거)는 [SS Heavy eight-concurrency validation(SS Heavy 8개 동시성 검증)](../evidence/2026-09-30-ss-heavy-eight-concurrency.md)에 남긴다.

그러나 1/2/4/8 전체 worker matrix(워커 행렬), sustained arrival(지속 도착), mixed corner(혼합 코너), timeout/cancel under load(부하 중 시간 초과/취소)는 아직 실행하지 않았으므로 scaling-limit(확장 한계)은 주장하지 않는다.

## STOP
이번 작업은 workload 재현, 규모/비용 분리, harness 준비까지만 한다. worker scaling과 fault injection은 실행하지 않는다.
