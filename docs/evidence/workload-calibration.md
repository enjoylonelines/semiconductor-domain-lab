# Workload calibration evidence

상태: **Phase 0~4 calibration 완료 / worker scaling 및 fault injection 미실행**.

## 환경
- base HEAD: `a078819e0c9d91276f43b21f86a617f02c980261`
- OpenSTA 3.1.0, revision `396536743ff33852cd8af176988f077219bc8b8d`
- Yosys 0.69+post
- SKY130 TT Liberty SHA256: `70a45bf9b5ea8f6a701dc34744b5c767b38e1af31b1d1f97309a97ec64603ecf`
- macOS arm64, `/usr/bin/time -l`
- OpenSTA만 calibration에 포함. RTL→mapped netlist 합성 시간은 worker workload에서 제외.

## 결과
| workload | 실제 구조 | valid repeats | wall median | wall p95 | max peak RSS | report bytes(대표) |
|---|---:|---:|---:|---:|---:|---:|
| Small | tiny, 3 mapped cells | 6 | 0.21s | 0.2375s | 53,166,080 | 12,211 |
| Medium | PicoRV32, 6,404 mapped cells | 6 | 0.33s | 0.355s | 76,414,976 | 29,468 |
| Heavy | PicoRV32 ×64, effective 409,856 mapped cell instances | 5 | 6.83s | 7.194s | 1,279,049,728 | report path count bounded |

Heavy report byte 수가 Medium보다 작은 것은 report command가 출력 path 개수를 제한하기 때문이다. workload 크기 지표로 report bytes를 사용하지 않는다.

Small raw real: 0.24, 0.21, 0.21, 0.23, 0.20, 0.21s.
Medium raw real: 0.36, 0.33, 0.34, 0.33, 0.32, 0.33s.
Heavy 후보 ×16 raw real: 1.94, 1.92, 1.91, 1.90, 1.91s. ×32는 3.39, 3.39, 3.38, 3.31, 3.78s로 사전 목표 5~15s에 못 미쳐 확장했다. 최종 Heavy ×64 raw real: 7.21, 7.13, 6.64, 6.83, 6.56s. 목표 구간에 처음 진입했으므로 더 키우지 않았다.

첫 PicoRV32 probe는 unsupported Tcl command `remove_from_collection` 때문에 timing report 전에 종료되어 **폐기**했으며 위 집계에 포함하지 않았다.

## 후보 탈락
OpenSTA upstream GCD는 약 1,292 SKY130 cell references가 있지만 동일 timing-report 조건에서 0.21~0.22s였다. Small과 wall-clock이 명확히 분리되지 않아 Medium 명칭을 부여하지 않았다.

Ibex는 공개·Apache-2.0 후보지만 공식 문서상 Yosys 직접 입력 제약이 있고 sv2v 경로가 필요하다. PicoRV32가 단일 Verilog + Yosys + 기존 Liberty로 재현되어 이번 dependency budget에서는 보류했다.

## 출처/라이선스
PicoRV32: YosysHQ/picorv32 pinned `ef203c2b0a3fb793280f5114941416c425c5b461`, ISC. 원본 `picorv32.v` SHA256 `0836050971b3c6cdd28ac3b1e5719a67fb645161912bef1e472e63995ceb0622`.
OpenSTA GCD/Liberty는 pinned OpenSTA checkout의 examples를 사용한다. 외부 source checkout과 대형 Liberty/netlist는 repo에 vendoring하지 않고 revision/hash로 고정한다.

## 재현
`python3 benchmark/prepare_opensta_workloads.py`

`python3 benchmark/run_opensta_workload_benchmark.py --workload all --repeats 5`

harness canonical raw output: `benchmark/raw/`.
현재 수동 calibration raw는 `/tmp`에 있으며 요약값은 `docs/evidence/workload-calibration.json`에 보존했다. harness는 fault injection이나 Cycle 1 제품 코드를 호출하지 않는다.

## 측정하지 못했거나 아직 주장할 수 없는 것
- net count와 timing endpoint/path population은 이번에 안정된 공통 counting 방법을 등록하지 못해 미측정.
- worker 1/2/4/8 scaling, throughput, concurrent p50/p95 latency 미측정.
- CPU saturation/memory pressure/DB coordination scaling limit 미측정.
- worker SIGKILL, recovery time, failure overhead 미측정.
- 따라서 “worker N개가 최적”, “N% 빨라졌다”, “장애에도 안전하다”는 아직 주장할 수 없다.
- Heavy는 production workload/대규모 EDA/실무 규모의 증거가 아니다. 공개 CPU RTL을 64개 반복 인스턴스화한 calibration fixture다.
- 8개 Heavy worker가 동시에 각 1개 job을 실행할 때의 메모리는 아직 측정하지 않았다. 단일 job peak RSS를 단순 곱한 값을 실제 동시 실행 메모리라고 주장하지 않는다.

## STOP 확인
1. Medium/Heavy가 실제 OpenSTA에서 재현됨: 충족.
2. Small/Medium/Heavy 비용 차이 실측: 충족. Medium의 wall 증가는 작지만 cell/RSS와 wall 모두 Small보다 증가했고 Heavy는 명확히 분리됨.
3. reproducible harness: 준비됨.
4. Cycle 1 제품 코드 수정: 0건.
5. worker scaling/fault 최종 비교: 미실행.

다음 gate는 Cycle 1 종료 후 Phase 5 실행 승인이다.
