# 10G PCS domain fixture vs load fixture decision

## 문제
지원 대상의 고속 인터페이스 IP 도메인과 OpenSTA worker scaling workload를 하나의 fixture로 통합할 수 있는지 검토했다.

## 조사/실험
MIT 라이선스의 alexforencich/verilog-ethernet pinned revision `77320a9471d19c7dd383914bc049e02d9f4f1ffb`에서 10GBASE-R 관련 RTL을 확인했다.

- `xgmii_baser_enc_64`: Yosys generic synthesis 1,920 cells, 약 0.16s.
- `xgmii_baser_dec_64`: Yosys generic synthesis 1,834 cells, 약 0.16s.
- `eth_phy_10g_tx_if + lfsr`: 180s budget 내 generic synthesis 미완료.
- `read_verilog + hierarchy`로 범위를 줄여도 120s budget 내 미완료.
- LFSR는 58-bit scrambler/64-bit parallel data 및 31-bit PRBS 경로를 parameterized combinational logic으로 전개한다.

따라서 현재 관측된 장시간은 OpenSTA timing 계산이 아니라 Yosys elaboration/synthesis 경로에서 발생한다. 이를 근거 없이 “10G STA가 무겁다”로 해석하지 않는다.

## 결정
1. **Domain fixture**: 10G PCS의 합성 가능한 64b/66b encoder/decoder 등 디지털 블록. 인터페이스 IP/PCS 구조와 RTL→EDA 흐름 학습용.
2. **Load fixture**: PicoRV32 × N. OpenSTA 계산량을 통제하고 worker scaling/resource contention/recovery를 측정하는 용도.
3. 10G 전체 PHY를 Heavy로 만들기 위해 upstream LFSR RTL을 변형하거나 Yosys 최적화 프로젝트로 확장하지 않는다.
4. PicoRV32를 지원 회사 제품/업무 재현이라고 주장하지 않는다.
5. 10G fixture 역시 상용 PHY, analog SERDES, sign-off 또는 지원 회사의 실제 IP를 재현한다고 주장하지 않는다.

## 변경된 판단
초기에는 도메인 fixture와 Heavy workload를 10G PCS 하나로 통합할 가능성을 검토했다. 실측 결과 합성 병목과 STA workload를 분리할 수 없었으므로 실험 변수 오염을 피하기 위해 두 목적을 분리한다.

## Stop condition
10G 전체 PHY의 Yosys 합성 최적화는 여기서 종료한다. Cycle 1 이전에는 load fixture calibration/harness의 독립 검증만 허용하며 ownership/recovery/fault 코드는 수정·실행하지 않는다.
