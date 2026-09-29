# 10G PCS domain fixture evidence

목적은 지원 대상의 고속 인터페이스 IP와 가까운 공개 디지털 PCS RTL을 실제 RTL→gate-level→STA 흐름으로 확인하는 것이다. 성능 Heavy workload나 상용 PHY sign-off를 주장하지 않는다.

## Source
- alexforencich/verilog-ethernet revision `77320a9471d19c7dd383914bc049e02d9f4f1ffb`
- MIT license
- blocks: `xgmii_baser_enc_64`, `xgmii_baser_dec_64`
- Yosys 0.69+post, SKY130 TT Liberty SHA256 `70a45bf9b5ea8f6a701dc34744b5c767b38e1af31b1d1f97309a97ec64603ecf`
- OpenSTA 3.1.0

## Synthesis
| block | generic cells | SKY130 mapped cells | Yosys mapped synthesis |
|---|---:|---:|---:|
| 64b/66b encoder | 1,920 pre-techmap / 1,066 post generic optimization | 632 | ~0.84s observed |
| 64b/66b decoder | 1,834 pre-techmap / 1,215 post generic optimization | 692 | ~0.52s observed |

숫자는 전체 10G PHY가 아니라 두 PCS 디지털 블록만 의미한다.

## OpenSTA vertical slice
Yosys 기본 `write_verilog` 결과에는 OpenSTA Verilog reader가 거부하는 `wire signed [31:0] i`가 남았다. 제품 RTL을 수정하지 않고 STA fixture 생성 단계에 `splitnets -ports`를 적용해 loop integer 잔여 표현이 제거된 gate netlist를 생성했다.

학습용 constraint:
- clock: 6.4ns
- input/output delay: 0.5ns
- input transition: 0.1
- output load: 0.05

결과:
- encoder: OpenSTA exit 정상, worst slack max +3.31ns, wall 약 0.24s
- decoder: OpenSTA exit 정상, worst slack max +3.06ns, wall 약 0.23s

이 slack은 임의의 최소 학습 constraint에서 얻은 값이며 10GbE 규격 충족, PHY sign-off, 실제 PVT/parasitic 조건을 뜻하지 않는다.

## Full PHY experiment stop
`eth_phy_10g_tx_if`의 58-bit/64-bit parallel scrambler 및 PRBS LFSR elaboration이 현재 Yosys flow에서 120~180s budget을 넘겼다. 이는 OpenSTA workload가 무겁다는 증거가 아니므로 전체 PHY를 Heavy fixture로 승격하지 않았다. Yosys/LFSR 최적화는 별도 프로젝트로 확장하지 않고 STOP한다.
