# 실제 STA 입력 경로 조사·검증 계약

- 기준: main bb4997bfa46ca63d112866b029ceca3569fdfba8, 기존 service.py/tests 및 문서 미커밋 변경 보존.
- Observed problem: parser.py는 SYNTHETIC marker와 key=value를 요구한다. 실제 EDA report 입력 증거가 필요하다.
- Human hypothesis / Prediction: unrecorded.
- AI hypothesis: OpenSTA standalone netlist + Liberty + SDC가 가장 작은 실제 report fixture 공급원이다. RTL부터 설명하기 위해 Yosys 합성을 별도 비교할 수 있다.
- Baseline: 기존 synthetic parser. Challenger A: 실제 OpenSTA report 직접 입력 시 거절 확인. Challenger B: Yosys RTL→mapped netlist→동일 OpenSTA.
- Invariant: 실제 결과를 synthetic으로 위장하지 않는다. tool execution/parse/check를 분리한다. 기존 제품 코드와 변경사항을 보존한다.
- Budget: 환경 탐색, native OpenSTA 설치/build 1회(환경 조정 최대 1회), tiny design 1개, setup 조건 2개 이내, parser 연결 점검 1회. 설치/build 총 20분 이내 목표. 불가능하면 실제 장애 로그와 재현 경로를 남긴다.
- Falsification: 필수 의존성/라이선스/셀 매칭 불명, report 미생성, 유효 timing path 없음이면 실행 가능 claim을 기각한다.
- Decision required: standalone actual-report parser slice를 먼저 채택할지, synthesis를 필수 경로로 포함할지, 또는 보류할지.
- Stop: 공식 출처/실측 환경/원본 report 또는 실패 로그/field mapping/후속 acceptance 기준을 기록하고 Decision Gate. 제품 parser 변경, P&R, async 확장 없음.
- Human decision: option A (fixed netlist + Liberty + SDC → OpenSTA → parser/store) selected by user on 2026-09-24.
- Changed belief: pending human reflection.

## 실행 결과

[실행 증거 및 Decision Gate](../evidence/2026-09-24-real-sta/README.md)에 설치, RTL→합성→STA, 두 clock 조건, parser/service 거절 결과를 기록했다. 정상 +9.459949ns와 위반 -0.440050ns 모두 process exit=0. OpenSTA 단독 slice 우선은 사용자 선택으로 구현했고, [implementation result](../evidence/2026-09-24-real-sta/implementation-result.md)와 [decision](../decisions/2026-09-24-opensta-setup-max-slice.md)에 결과를 기록했다.
