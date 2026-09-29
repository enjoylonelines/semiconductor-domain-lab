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

Heavy ×64는 Supervisor(감독자) 경로에서 actual OpenSTA(실제 OpenSTA) `SUCCEEDED/TRUSTED`까지 확인했다. 그러나 현재 Docker Linux VM(도커 리눅스 가상 머신)은 총 약 1.91 GiB memory(메모리)이고 기본 Supervisor limit(감독자 제한)은 384 MiB여서, 기본 프로필에서는 Heavy가 OOM(메모리 부족)으로 종료됐다. test-only 1,500 MiB Supervisor limit(테스트 전용 1,500 MiB 감독자 제한)에서 one-worker baseline(단일 워커 기준선)만 통과했다.

따라서 현재 환경에서는 1/2/4/8 worker matrix(워커 행렬)를 실행하거나 scaling-limit(확장 한계)을 주장하지 않는다. 자세한 record(기록)는 [Phase 5 Heavy Supervisor smoke evidence(단계 5 고부하 감독 실행 스모크 근거)](../evidence/2026-09-29-phase5-heavy-supervisor-smoke.md)에 남긴다.

## STOP
이번 작업은 workload 재현, 규모/비용 분리, harness 준비까지만 한다. worker scaling과 fault injection은 실행하지 않는다.
