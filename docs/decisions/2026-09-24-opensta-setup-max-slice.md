# OpenSTA setup/max parser slice decision

작성일: 2026-09-24  
상태: 구현 완료, 다음 확장은 pending human decision.

## Decision

사용자는 [실제 STA 입력 경로 조사](../evidence/2026-09-24-real-sta/README.md)의 선택지 A를 채택했다.

고정된 mapped netlist, Liberty, SDC로 생성한 OpenSTA 3.1.0 single-path setup/max report만 지원한다. Yosys synthesis는 fixture 재생성 및 학습 경로이며 product execution의 필수 단계로 넣지 않는다.

## Implemented contract

- report banner는 OpenSTA 3.1.0, time unit은 1ns, path type은 max, 종료 marker는 EDA_LAB_REPORT_END여야 한다.
- startpoint, endpoint, path group, arrival/required time, path slack, worst slack, tool revision과 raw SHA256을 정규화한다.
- report의 summary 산술, slack label/sign, path slack/worst slack의 일치를 검증한다.
- timing violation은 execution success 및 parse success와 분리되어 check FAIL로 보존된다.
- adapter가 관측한 nonzero process exit는 report 내부 주장보다 우선하며 run FAILED로 보존된다.
- truncated, unsupported version, diagnostic error, inconsistent summary는 INVALID/UNKNOWN으로 저장된다.

## Evidence

- [actual OpenSTA MET report](../evidence/2026-09-24-real-sta/normal.log)
- [actual OpenSTA VIOLATED report](../evidence/2026-09-24-real-sta/tight.log)
- [implementation validation](../evidence/2026-09-24-real-sta/implementation-result.md)
- [parser implementation](../../src/eda_lab/parser.py)
- [OpenSTA regression tests](../../tests/test_opensta_report.py)

## Exclusions

This does not support hold/min, multiple path groups, multiple corners, SPEF, arbitrary OpenSTA versions, arbitrary Tcl scripts, live subprocess execution, or production/sign-off claims.

## Human decision / Changed belief

- Human decision: option A selected by user on 2026-09-24.
- Changed belief: pending human reflection.
- Next decision: whether the bounded parser closure is enough to proceed to the already-scoped async failure experiment. Do not start that experiment automatically.
