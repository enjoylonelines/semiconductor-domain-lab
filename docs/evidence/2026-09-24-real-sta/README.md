# 실제 RTL → STA report 경로: 조사·실행 증거와 Decision Gate

작성일: 2026-09-24. 상태: **검증 및 bounded parser slice 구현 완료**.
기준 저장소: `/Users/hb/Projects/semiconductor-domain-lab`, `main@bb4997bfa46ca63d112866b029ceca3569fdfba8`.
[실험 전 계약](../../plans/2026-09-24-real-sta-feasibility.md) · [범위·깊이 기준](../../plans/2026-09-24-scope-depth-closure-review.md).

## 결론

DevSpace Max의 macOS arm64에서 **SystemVerilog RTL → Yosys 합성 → SKY130 mapped Verilog netlist → OpenSTA → 실제 setup report**를 실행했다. 확보한 netlist를 고정하면 이후 실행에는 Yosys 없이 OpenSTA + Liberty + SDC만 필요하다.

사용자는 **고정 netlist 기반 OpenSTA setup report 한 계열의 parser correctness부터 닫기**를 채택했다. 합성은 fixture 재생성/학습 경로로 남긴다. 실제 포맷 parser와 replay adapter 경계는 [implementation result](implementation-result.md)에 기록한 범위로 구현했다.

| 클럭 주기 | 도구 exit | arrival (ns) | required (ns) | slack (ns) | 원문 판정 | 현재 parser → service |
| --- | --- | --- | --- | --- | --- | --- |
| 10ns | 0 | 0.423375 | 9.883325 | +9.459949 | MET | INVALID / UNKNOWN → FAILED |
| 0.1ns | 0 | 0.423375 | -0.016675 | -0.440050 | VIOLATED | INVALID / UNKNOWN → FAILED |

이는 연구용 tiny design의 **실제 도구 출력**이다. 생산 회로, sign-off, 제조 가능성, silicon correctness 증거는 아니다. 두 report는 동일 netlist/library를 사용하며 clock period만 다르다.

## 1. 저장소 상태와 문제 연결

현재 구조는 `runner.py`의 SyntheticTimingAdapter → `parser.py`의 parse_report → ParseResult → `service.py`의 JobService → `store.py`의 SQLite 저장이다. API, hardware adapters/clients와 별도 load 도구도 있지만 이번 경로에 필요하지 않다.

parser는 첫 줄 synthetic marker와 fixture_format_version/run_id/stage/corner/tool_exit_code/worst_slack의 key=value 입력을 요구한다. 실제 OpenSTA는 path block과 숫자 열을 출력하므로 그대로 넣으면 거절된다. [실측 boundary 결과](parser-service-boundary.json)는 production parse_report와 JobService를 사용하되, adapter는 **보존 report를 반환하는 replay**, 저장은 **in-memory SQLite**다. HTTP 요청이나 서비스 내부의 live subprocess 실행 검증은 아니다.

종료 점검 중 외부 동시 작업으로 AdapterRunResult(artifact_path, process_exit_code) 계약이 models/runner/service에 추가됐다. 서비스는 bare Path를 임시 diagnostic bridge로 받고 실제 process exit를 모르면 UNKNOWN으로 다루도록 변경 중이다. 이 작업은 해당 제품 코드를 수정하지 않았다. 동일 boundary probe를 새 상태에서 1회 재검증했으며 결과 JSON은 최초와 동일했다([최종 probe](parser-service-boundary-final.json)). 후속 live adapter는 새 AdapterRunResult 계약에 맞춰야 한다. 본 probe는 parse-invalid 경로 검증이므로 live execution 계약 검증을 대신하지 않는다.

두 raw report 모두 INVALID/UNKNOWN, service FAILED/parse_invalid, metrics 없음으로 저장됐다. false PASS는 없었다. 그러나 INVALID provenance의 source_kind가 synthetic으로 고정된다. 실제 입력의 출처를 잘못 표시하는 연결 지점이며 이후 포맷 dispatch/provenance 설계 시 분리해야 한다.

작업 전부터 service.py, tests/test_stage1.py가 수정되어 있었고 AGENTS/docs/uv.lock도 미추적 상태였다. 모두 보존했다. 기존 scope review의 “uv.lock만 미추적” 서술은 현재 상태가 아닌 과거 관측이다. 이번 변경은 새 계획·증거 파일뿐이며 commit/push하지 않았다.

## 2. 후보 역할·설치·라이선스

아래 설치 난이도는 이 slice 기준 AI 평가다. 공식 자료 조회일은 2026-09-24이며, 웹의 최신 branch와 실제 실행 버전을 구분한다.

| 도구 | 역할과 출력 | 라이선스/공식 출처 | macOS arm64 및 이번 확인 |
| --- | --- | --- | --- |
| Yosys | RTL elaboration/synthesis, Liberty 셀 매핑, mapped Verilog 및 합성 log | [ISC, third-party 별도](https://github.com/YosysHQ/yosys) | 낮음: [Homebrew](https://formulae.brew.sh/formula/yosys) arm64 bottle 실제 설치, 0.69+post 실행 성공 |
| OpenSTA | gate-level STA, setup/hold path 및 slack report; behavioral RTL 합성기는 아님 | [GPL v3 계열 / 상용 dual licensing](https://github.com/parallaxsw/OpenSTA) | 중간: 기본 brew formula 없음. CMake/CUDD/Tcl 등 native build 성공, Mach-O arm64 확인 |
| OpenROAD | 물리설계, clock tree, routing 및 OpenSTA 통합 분석; flow scripts로 Yosys와 연결 | [BSD-3-Clause](https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/LICENSE), 포함 의존성 별도 | 높음: [공식 설치](https://openroad.readthedocs.io/en/latest/user/Build.html)는 현재 Bazel 중심, macOS 안내 존재. arm64 전체 build/run은 이번에 미검증 |
| Icarus Verilog | Verilog simulation, testbench 실행, 기능 로그/VCD; 셀 timing STA 대체 아님 | [주로 GPL, 일부 LGPL](https://github.com/steveicarus/iverilog) | 낮음: [brew formula](https://formulae.brew.sh/formula/icarus-verilog) 13.0/arm64 제공 확인, 설치·실행 미수행 |
| Verilator | Verilog/SystemVerilog compile/lint/simulation, C++ 모델·기능 로그 | [LGPL-3.0 또는 Artistic-2.0](https://verilator.org/guide/latest/faq.html) | 낮음~중간: [brew formula](https://formulae.brew.sh/formula/verilator) 5.052/arm64 제공 확인, 설치·실행 미수행 |

Yosys 최신 upstream의 SystemVerilog 지원 확대와 설치한 frontend 지원은 동일하다고 가정하지 않는다. 이번에는 `read_verilog -sv`로 logic/always_ff의 작은 synthesizable subset만 확인했다. 임의 SystemVerilog, interfaces/classes, 모든 IP 소스 호환은 미검증이다. [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build)는 darwin-arm64 배포 대안이나 이번엔 추가 suite 설치가 필요 없었다.

OpenROAD/P&R은 scope review의 확장 중단 항목이다. Icarus/Verilator의 기능 검증은 별도 가치가 있지만 report correctness를 위한 필수 dependency는 아니다. 도구의 라이선스가 design/library 파일의 라이선스를 자동 결정하지 않으므로 각각 출처와 notice를 유지한다.

## 3. 최소 flow와 파일별 의미

```text
tiny.sv + SKY130 Liberty
    → Yosys read_verilog / synth / dfflibmap / abc
    → tiny_mapped.v + synthesis.log
tiny_mapped.v + 동일 Liberty + normal.sdc 또는 tight.sdc
    → OpenSTA read_liberty / read_verilog / link_design / read_sdc
    → report_units + check_setup + report_checks + report_worst_slack
    → raw stdout log + subprocess exit/stderr metadata
    → [후속 선택] OpenSTA 전용 parser → ParseResult → service/store
```

- **RTL**: clk/a/b/y 포트, 내부 q register, 매 clock에서 q<=a, y<=q XOR b. 자체 작성한 작은 연구 fixture다.
- **Mapped netlist**: instance/cell/pin/net의 연결. 실제 합성 결과는 sky130_fd_sc_hd__dfxtp_1 2개, xor2_1 1개다. OpenSTA는 이러한 구조적 Verilog를 읽는다.
- **Liberty**: cell timing arcs, clock-to-Q, setup/hold, capacitance, slew/load table, 단위 및 operating condition. 사용 파일은 tt_025C_1v80, time 1ns/capacitance 1pF. 합성과 STA가 같은 파일을 써야 셀/핀 정의가 일치한다.
- **SDC**: clock period, input/output max/min delay, input transition, output load. 이번엔 10ns/0.1ns 두 조건. 순수 Yosys synth script가 STA SDC 전체를 소비하는 것은 아니다. 이번 합성에는 SDC를 전달하지 않았다.
- **SPEF**: 추출된 wire RC를 추가할 때 필요. 이번에는 없음. net delay가 0인 ideal pre-layout 결과이며 배치배선 지연을 검증하지 않는다.
- LEF/DEF/GDS, testbench, VCD는 이 setup report 생성에 필수 입력이 아니다. VCD는 시뮬레이션/활동률, GDS는 물리 구현과 관련된다.

Setup max 분석은 동일 조건에서 required-arrival이 slack이다. Hold min 분석은 의미/산술 방향이 다르므로 이 포맷 slice에 섞지 않는다. 한 group의 대표 worst path와 전체 디자인·모든 corner 통과는 다른 주장이다.

## 4. 공개 입력 출처와 보존 방식

| 자산 | 확보 출처/조건 | 이번 사용 |
| --- | --- | --- |
| RTL/SDC | 이 디렉터리 tiny.sv, normal.sdc, tight.sdc: 외부 IP 복사 없이 작성 | 사용·보존 |
| 공개 RTL/netlist/constraint 예제 | [OpenSTA examples](https://github.com/parallaxsw/OpenSTA/tree/396536743ff33852cd8af176988f077219bc8b8d/examples): gcd_rtl.v, gcd_sky130hd.v/.sdc 등. [저장소 LICENSE](https://github.com/parallaxsw/OpenSTA/blob/396536743ff33852cd8af176988f077219bc8b8d/LICENSE) 및 개별 notice 보존 | 대안으로 확인, 이번 toy design으로 대체 |
| 실제 사용 Liberty | [OpenSTA의 sky130hd_tt.lib.gz](https://github.com/parallaxsw/OpenSTA/blob/396536743ff33852cd8af176988f077219bc8b8d/examples/sky130hd_tt.lib.gz), revision 고정 | 다운로드한 source checkout에서 실행. 대형 library는 이 repo에 복제하지 않고 URL/해시 보존 |
| SKY130 원출처 | [Google/SkyWater HD library](https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd), [Apache-2.0 LICENSE](https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd/blob/main/LICENSE) | library provenance 참고. OpenSTA 가공 예제와 upstream 개별 파일 byte 동일성은 주장하지 않음 |
| Nangate45 대안 | [ORFS platform](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/tree/master/flow/platforms/nangate45), platform [Apache-2.0 LICENSE](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/master/flow/platforms/nangate45/LICENSE) | research/testing용 non-manufacturable library. OpenSTA 사본 header에 별도 제한 문구가 보여 이번 사용은 SKY130으로 한정 |

공개 접근 가능성과 임의 재라이선스는 구분한다. 현재 보존 대상은 자체 RTL/SDC, 생성 netlist/report/log와 재현 정보다. upstream 도구 소스/바이너리나 library를 배포물에 포함시키는 선택은 이번에 하지 않았다.

사용 Liberty gzip SHA256: `210e56be3a3a0907b5241a34d277f664cf4b4d91dcb49a27ff813df4406a5889`.
압축 해제 SHA256: `70a45bf9b5ea8f6a701dc34744b5c767b38e1af31b1d1f97309a97ec64603ecf`.
이 값이 달라지면 같은 증거로 취급하지 않는다.

## 5. 실제 설치와 실행

환경: DevSpace Max ws_76a2f3e4b8, Darwin arm64/macOS 26.7 (25G229). cloud computer/DevSpace Air 사용 없음.
최초 PATH에 sta/yosys/openroad/iverilog/verilator/cmake 없음. Docker CLI는 있으나 Colima socket이 없어 daemon 연결 실패. Docker를 시작하거나 image를 설치하지 않았다.

Homebrew 설치: yosys 0.69, cmake 4.4.3, swig 4.5.1, bison 3.8.2, flex 2.6.4_2, eigen 5.0.1, tcl-tk@8 8.6.18 및 yosys 의존성 libtommath/tcl-tk/tomlplusplus. 초기 cudd formula 포함 요청은 formula 부재로 실패했고 분리 설치했다. brew 자동 갱신도 발생했다. 설치 출력에서 Tcl9 link가 해제됐으므로 이후 다른 Tcl 사용자에게 이 환경 변화가 관련될 수 있다. shell startup 파일은 수정하지 않았다.

OpenSTA source `396536743ff33852cd8af176988f077219bc8b8d`, CUDD 3.0.0 source `f54f533303640afd5dbe47a05ebeabb3066f2a25`를 /tmp에 clone했다. OpenSTA executable version 3.1.0; Yosys git `143eb14f9cc55d6f8927e68523b0c9d2166ed02c`.
Native build는 Flex include 누락으로 최초 configure 실패 → 명시 경로 보정 1회. 60초 호출 제한으로 중단된 build를 같은 directory에서 이어 완성했다. build1/2/3.log를 보존했다. 이 로그는 도구 호출 출력 기록이며 전체 dependency install transcript는 아니다.

재현(깨끗한 clone 경로에서, 시스템별 Homebrew prefix 조정):
```sh
brew install yosys cmake swig bison flex eigen tcl-tk@8
git clone https://github.com/cuddorg/cudd.git /tmp/eda-cudd-20260924
git -C /tmp/eda-cudd-20260924 checkout f54f533303640afd5dbe47a05ebeabb3066f2a25
cd /tmp/eda-cudd-20260924
./configure --enable-shared --enable-obj
make -j4
git clone https://github.com/parallaxsw/OpenSTA.git /tmp/eda-opensta-20260924
git -C /tmp/eda-opensta-20260924 checkout 396536743ff33852cd8af176988f077219bc8b8d
PATH=/opt/homebrew/opt/bison/bin:/opt/homebrew/opt/flex/bin:$PATH cmake \
  -S /tmp/eda-opensta-20260924 -B /tmp/eda-opensta-20260924/build \
  -DCUDD_INCLUDE=/tmp/eda-cudd-20260924/cudd \
  -DCUDD_LIB=/tmp/eda-cudd-20260924/cudd/.libs/libcudd.a \
  -DTCL_LIBRARY=/opt/homebrew/opt/tcl-tk@8/lib/libtcl8.6.dylib \
  -DTCL_INCLUDE_PATH=/opt/homebrew/opt/tcl-tk@8/include \
  -DFLEX_INCLUDE_DIR=/opt/homebrew/opt/flex/include \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build /tmp/eda-opensta-20260924/build -j4
gzip -dk /tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz
cd /Users/hb/Projects/semiconductor-domain-lab/docs/evidence/2026-09-24-real-sta
yosys -Q -T -q -l synthesis.log -s synth.ys
EDA_LIB=/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz \
EDA_SDC=normal.sdc /tmp/eda-opensta-20260924/build/sta -no_init -exit run.tcl
# tight.sdc로 동일 실행. stdout/stderr/returncode를 별도로 보존한다.
```

`-no_init`는 사용자 .sta init 영향을 배제한다. 출력 끝의 EDA_LAB_REPORT_END는 **우리 Tcl이 추가한 완료 marker**이며 OpenSTA 표준 포맷이 아니다. marker 하나만으로 Tcl 중간 오류 부재를 보장하지 않는다. 이후 runner는 진단 오류, exit, report 구조를 함께 검증해야 한다.

합성 최초 실행은 Liberty black-box 정의를 읽지 않아 마지막 check에서 y driver 경고가 발생했다. `read_liberty -lib`를 추가하고 `check -assert`로 재실행하니 0 problems. 초기 synthesis-initial.log도 보존했다. ABC combinational network/multi-output library 안내는 남아 있고, 최종 netlist는 실제 STA에서 link·분석됐다. formal equivalence나 simulation 검증은 하지 않았다.

## 6. 실제 포맷 → parser/service 필드

| 원문 또는 실행 근거 | 제안 normalized 필드 | 검증/주의 |
| --- | --- | --- |
| banner OpenSTA 3.1.0 + sha | tool_name/version/revision | 지원 버전·명령 profile 고정 |
| report_units의 time 1ns | original_unit, unit_scale, *_ns | 숫자 모양으로 ns를 추측하지 않음 |
| Startpoint/Endpoint | startpoint, endpoint | 이번 _3_ → _2_, mapped netlist로 추적 |
| Path Group: clk | path_group | 단일 group 범위 |
| Path Type: max | analysis_type=setup_max | min/hold와 분리 |
| data arrival/required time | arrival_time_ns, required_time_ns | 반복 summary 행과 per-pin delay 열 구별 |
| 9.459949 slack (MET) 등 | reported_path_slack_ns, reported_check_status | 수치 부호와 label 일치 확인 |
| worst slack max | worst_slack_ns, analysis_scope | path 최소값을 전체 design worst로 임의 승격하지 않음 |
| subprocess returncode/stderr | execution_status, tool_exit_code, diagnostics | timing violation에도 exit 0 실제 관측 |
| 호출 manifest 및 입력 해시 | run_id, corner, flow_name, input_sha256 | report에 없는 값을 외부 metadata로 명시 |
| raw bytes + Tcl 완료 marker | source_sha256, completeness | marker/필수행/중복/유한수/진단 모두 확인 |
| 실제 도구 생성 사실 | source_kind=tool_generated | 회로 자체는 toy fixture라는 provenance 함께 저장 |

raw [normal.log](normal.log), [tight.log](tight.log)는 banner/units/path/summary/marker까지 stdout 원문을 보존한다. stderr와 exit는 각각 *-execution.json에 있다. 정상 path의 _3_/Q clock-to-Q 0.281003, XOR arc 0.142373을 추적할 수 있다.

독립 **수기 전사 oracle**는 정상 required 9.883325 − arrival 0.423375 ≈ slack 9.459949, 위반 -0.016675 − 0.423375 = -0.440050을 확인한다. 6자리 출력 반올림을 고려한 0.000002ns tolerance를 사용한다. verify_boundary.py는 이 전사값/산술/summary 일치와 기존 parser 거절을 검증한다. 다른 STA 엔진과 수치 교차 검증한 것은 아니다.

현재 모델은 worst_slack 위주이며 path scope/analysis type/tool-generated provenance가 부족하다. 후속 구현은 기존 synthetic 입력 형식을 재사용하는 위장 변환 대신 포맷을 명시적으로 선택하고 실행 metadata를 별도로 결합해야 한다. JobSpec의 worst_slack 입력은 synthetic 전용이라는 점도 live tool 입력과 분리할 필요가 있다.

## 7. 가장 작은 vertical slice 비교

| 선택 | 포함 | 장점 | 추가 부담/현재 결과 |
| --- | --- | --- | --- |
| A: 고정 netlist + lib + SDC → OpenSTA → parser/store | 이번 mapped netlist/두 setup report와 단일 profile | 핵심 P0의 실제 report·원문 추적·누락/실패 경계를 바로 검증 | AI 추천. 생성 성공, 현재 parser는 미지원 |
| B: RTL → Yosys → A를 항상 수행 | 합성 frontend, 셀 매핑과 합성 failure도 제품 실행 경로에 포함 | RTL부터 end-to-end 설명 가능 | 실행 가능은 확인. synthesis 버전/변환/오류 계약이 제품 범위를 넓힘 |
| C: OpenROAD P&R 포함 | placement/routing/parasitics 및 STA | 실제 배선 영향 비교 가능 | 현재 목적에 불필요, 미실행·보류 추천 |

scope review P0-5(실제 report 계열 및 재현 자료)와 P0-6의 **지원 parser 정규화 oracle 일치**는 이 bounded profile에서 완료했다. 구현은 [implementation result](implementation-result.md), 결정은 [decision](../../decisions/2026-09-24-opensta-setup-max-slice.md)에 기록했다. P1 async failure와 프로젝트 전체 종료 조건은 완료로 표시하지 않는다.

A 채택 시 후속 acceptance 제안:
1. OpenSTA 3.1.0 pinned setup/max, 단일 clk/TT/no-SPEF profile만 명시 지원.
2. 두 원본에 대해 start/end/group/type/unit/arrival/required/slack/provenance를 oracle과 대조.
3. exit!=0, 진단 error, marker/필수행 누락, 중복 path/summary, unsupported profile/version, NaN/Inf 반례를 PASS로 승격하지 않음.
4. exit=0 & negative slack은 execution 성공/parse OK/check FAIL을 보존. unsupported/불완전은 UNKNOWN.
5. 원문 hash와 input/config/tool revision, process exit 및 분석 범위를 저장까지 추적.
6. 동일 자료 재검증 후 STOP. 새 vendor, P&R, async/queue는 자동 착수하지 않음.

## 8. Decision Gate — 선택 및 구현 결과

- **A 채택**: OpenSTA 단독 actual-report parsing/validation slice를 구현했다. Yosys는 fixture 생성 근거로 유지한다.
- **B 미채택**: RTL부터 synthesis를 필수 제품 경로로 넣지 않았다.
- **C 미채택**: 구현 보류를 선택하지 않았다.

Human hypothesis / Prediction: unrecorded.
Human decision: option A selected by user on 2026-09-24.
Changed belief / 최종 프로젝트 종료 판단: pending human decision.
이번 bounded slice stop condition: 실제 report 두 개의 parser/service normalization, invalid regression, raw artifact provenance와 execution/check 분리 검증 완료. P1 async failure는 자동 착수하지 않는다.

## Evidence index

- tiny.sv / synth.ys / tiny_mapped.v: 원입력, 합성 절차, 생성 결과.
- normal.sdc / tight.sdc / run.tcl: 동일 회로 분석 조건과 실제 실행 명령.
- synthesis-initial.log / synthesis.log: 최초 경고 및 보강 후 로그.
- build1.log / build2.log / build3.log: configure 실패, 재개 전 build, 완성 기록.
- normal.log / tight.log 및 *-execution.json: raw report/실행 결과.
- verify_boundary.py / parser-service-boundary.json: 원문 oracle·현재 parser/service probe.
- manifest.json: 입력/로그/관련 제품 파일 SHA256 및 환경 식별.

재현 도구와 library는 /tmp checkout에 있어 시스템 정리 시 사라질 수 있다. 보고서/입력/생성 netlist는 repo에 남는다. pinned source와 해시로 tool/library를 다시 확보할 수 있다. 성능·대규모 처리·hold/multi-corner/비정상 subprocess 수명은 미측정이다.
