# 퀄리타스반도체 SW Engineer 도메인 학습 가이드

작성일: 2026-09-23  
목적: 반도체 설계자가 되는 것이 아니라, 퀄리타스반도체의 SW Engineer가 어떤 하드웨어 개발 흐름과 데이터를 다루는지 설명할 수 있게 되는 것.

## 이 자료를 읽는 법

- **사실:** 공식 회사·채용·표준·EDA 자료에 직접 나온 내용
- **연결:** 공개된 사실을 SW 업무와 연결한 합리적 해석
- **단순화:** 이해를 위한 설명이며 실제 회사 내부 구현을 뜻하지 않음

자료를 읽은 뒤에는 화면을 닫고 확인 질문에 답한다.

## 1. 퀄리타스반도체가 하는 일

퀄리타스반도체는 **SoC와 칩렛 같은 시스템에서 데이터를 빠르게 주고받게 하는 인터페이스 IP를 개발·공급하는 회사**로 이해하면 된다.

공식 홈페이지는 SERDES PHY, PCIe Gen4~Gen6 PHY, UCIe PHY, MIPI C-PHY/D-PHY 및 디스플레이·USB·Ethernet PHY 제품군을 소개한다. 적용 분야로 AI, HPC, 데이터센터, 자동차, 임베디드 AI를 제시한다.

출처:

- [퀄리타스 공식 제품 홈페이지](https://q-semi.com/kr)
- [공식 고속 인터커넥트 IP 포트폴리오](https://www.q-semi.com/user/hisp/HIPC1000V)
- [공식 AI·HPC 적용 제품 설명](https://www.q-semi.com/user/appl/APAI1000V)

| 말 | 뜻 | SW Engineer가 알아야 할 수준 |
|---|---|---|
| SoC | CPU, 메모리 관련 블록, 인터페이스 등 여러 기능을 한 칩에 집적 | 칩 내부에 여러 IP가 연결된 구조 설명 |
| IP | 상위 칩에 통합할 수 있는 재사용 설계 자산 | 완제품 칩과 구분 |
| Interface | 블록·칩·장치가 데이터를 교환하는 규칙 | 데이터가 어디로 가는지 설명 |
| Controller | 프로토콜·제어 규칙을 처리하는 논리 블록 | 무엇을 보낼지의 역할 |
| PHY | 실제 전기 신호를 송수신하는 물리 계층 | 신호를 어떻게 보낼지의 역할 |
| SerDes | 병렬 데이터를 직렬로 보내고 다시 복원하는 기술 | 고속 링크와 신호 품질의 배경 이해 |

## 2. MCU에서 SoC와 IP로 내려가기

MCU는 마이크로컨트롤러다. 임베디드 개발자는 보통 센서·장치와 MCU를 연결하고 펌웨어로 제어한다.

    센서/장치 → SPI·I2C·UART → MCU → 펌웨어 → 제어·상태·로그

SoC는 여러 시스템 기능을 하나의 칩에 모은다.

    SoC
    ├─ CPU
    ├─ GPU/NPU 또는 가속기
    ├─ 메모리 컨트롤러
    ├─ PCIe/MIPI/UCIe 관련 IP
    └─ 기타 주변·보안·전원 블록

핵심 관점은 이것이다.

> 임베디드 개발자는 MCU를 부품으로 사용하지만, 반도체 IP 회사는 SoC 안에 들어갈 블록을 만든다.

IP는 소스코드 라이브러리와 같은 의미가 아니다. 반도체에서 IP는 RTL, 회로, 물리 설계 데이터, 모델, 검증 자료, 문서 등 여러 설계 자산의 묶음일 수 있다.

확인 질문:

1. MCU를 사용한 경험이 곧 PHY 설계 경험이 아닌 이유는?
2. SoC 안에 IP가 여러 개 필요한 이유는?
3. IP integration에서 연결 조건·제약·모델 버전을 확인해야 하는 이유는?

정답의 핵심:

- MCU 사용은 완성된 칩을 활용하는 일이고 PHY 설계는 칩 내부 회로·검증 자산을 만드는 일이다.
- 큰 칩을 기능 블록 단위로 재사용하고 통합하기 위해 IP가 필요하다.
- IP는 연결만 하면 끝나는 것이 아니라 설정·타이밍·전원·물리 조건과 검증 모델이 맞아야 한다.

## 3. PCIe·UCIe·MIPI·SerDes

이 네 단어는 같은 계층의 형제가 아니다.

### PCIe

PCIe는 프로세서·가속기·SSD 같은 장치 사이를 연결하는 인터페이스 계열이다. 퀄리타스는 PCIe Gen4~Gen6 PHY IP를 제품으로 소개한다.

학습 문장:

> PCIe는 장치 간 연결 규격이고, PCIe PHY는 그 규격을 실제 신호로 구현하는 IP의 한 부분이다.

### UCIe

UCIe는 패키지 안에서 서로 다른 칩렛(die)을 연결하기 위한 개방형 규격이다. PCIe와 모두 고속 연결이지만 물리 거리, 패키징, 계층 구조, 사용 목적이 다르다.

출처: [UCIe Consortium](https://www.uciexpress.org/), [UCIe 자료](https://www.uciexpress.org/ucie-resources)

### MIPI

MIPI는 하나의 단일 PHY가 아니라 모바일·카메라·디스플레이 등 여러 인터페이스 규격의 생태계다.

- CSI-2: 카메라 데이터 인터페이스
- DSI-2: 디스플레이 데이터 인터페이스
- D-PHY/C-PHY: 그 위에서 사용하는 물리 계층 선택지

MIPI 공식 문서는 D-PHY를 전달 클록과 데이터 레인을 사용하는 물리 링크로 설명하고, CSI-2와 DSI-2가 D-PHY 또는 C-PHY를 사용할 수 있음을 설명한다.

출처: [MIPI D-PHY](https://www.mipi.org/specifications/d-phy), [MIPI DSI-2](https://www.mipi.org/specifications/dsi-2), [MIPI CSI-2 자료](https://www.mipi.org/sites/default/files/MIPI_CSI-2_Specification_Brief.pdf)

### SerDes

SerDes는 Serializer/Deserializer의 줄임말이다.

    칩 내부 병렬 데이터
          ↓
    Serializer
          ↓
    고속 직렬 링크
          ↓
    Deserializer
          ↓
    상대편 칩 내부 병렬 데이터

고속 링크에서는 채널 손실과 잡음 때문에 equalization이 중요하다.

- CTLE: 연속 신호의 주파수 응답을 조정
- FFE: 송신 측에서 미리 보정
- DFE: 이전 판정을 이용해 수신 간섭을 보정
- eye diagram: 신호의 시간·전압 여유를 시각화
- BER: 관찰된 비트 중 오류 비율

출처: [퀄리타스 SerDes 제품](https://www.q-semi.com/user/hisp/HIPC1000V), [MathWorks SerDes](https://www.mathworks.com/help/serdes/design-and-simulate-serdes-systems.html), [Keysight BER·eye diagram](https://www.keysight.com/kr/ko/learn/course.receiver-and-bit-error-rate-testing-bert-basics.html)

세 문장으로 비교한다.

- PCIe는 시스템 장치 간 연결 규격이다.
- UCIe는 패키지 내 칩렛 간 연결 규격이다.
- MIPI는 카메라·디스플레이 연결 계열이며 CSI-2/DSI-2와 C-PHY/D-PHY를 구분해야 한다.

## 4. EDA workflow

EDA는 회로를 직접 연결하는 한 가지 프로그램이 아니라 설계·검증·구현을 돕는 도구와 흐름이다.

### 디지털 흐름

    요구사항
    → RTL 설계
    → simulation / functional verification
    → synthesis
    → floorplan
    → placement
    → clock tree synthesis
    → routing
    → timing·power·physical analysis
    → sign-off
    → tape-out용 데이터

- RTL: 레지스터 전송 수준의 설계 표현
- simulation: 모델에 입력을 넣고 동작을 계산
- verification: 요구사항을 만족하는지 확인
- synthesis: RTL을 게이트 수준 논리 구조로 변환
- P&R: 셀을 배치하고 연결 배선
- STA: 경로와 타이밍 제약을 계산
- slack: 요구 시간과 실제 도착 시간 사이의 여유
- sign-off: 정해진 검사 기준을 최종 검토
- tape-out: 제조용 최종 설계 데이터를 넘기는 이정표

출처: [OpenROAD Flow](https://openroad-flow-scripts.readthedocs.io/en/latest/mainREADME.html), [OpenROAD 튜토리얼](https://openroad-flow-scripts.readthedocs.io/en/latest/tutorials/FlowTutorial.html), [IDEC EDA 자료](https://www.idec.or.kr/edatool/intro/), [Synopsys EDA 흐름](https://www.synopsys.com/implementation-and-signoff/fusion-technology.html)

### 아날로그·PHY 흐름

    회로 사양
    → schematic
    → circuit simulation
    → layout
    → parasitic extraction
    → post-layout simulation
    → DRC/LVS·신뢰성·전원/신호 분석
    → sign-off

아날로그와 PHY를 디지털 RTL 흐름만으로 설명하면 부족하다. 디지털 제어 로직과 아날로그 송수신 회로가 함께 있는 경우 두 흐름과 모델이 연결된다.

### 가장 중요한 구분

EDA 작업이 정상 종료했다는 것은 도구 실행이 끝났다는 뜻이다.

파싱에 성공했다는 것은 SW가 파일 형식을 읽었다는 뜻이다.

설계 검사가 통과했다는 것은 특정 검사 기준을 만족했다는 뜻이다.

예: 도구 종료 코드 0, parser 성공, worst slack -0.08 ns라면 실행과 파싱은 성공했지만 timing 검사는 실패할 수 있다.

## 5. SW Engineer가 개입하는 지점

퀄리타스 공식 채용 공고에는 RESTful API, 메시지 큐, 관계형 DB, Redis Pub/Sub, 반도체 로그·리포트 파싱, 컨테이너 운영, DB migration, 레거시 리팩토링, CI/CD가 명시되어 있다. 과거 공고에는 HW 요구사항을 반영한 in-house tool, 업무 자동화, MCU firmware, Web programming도 명시되어 있다.

출처: [공식 SW Engineer 공고](https://q-semi.career.greetinghr.com/ko/o/212725), [SW Engineer 공고](https://www.wanted.co.kr/wd/368416), [과거 HW 협업 공고](https://www.wanted.co.kr/wd/217418)

학습용 연결 모델:

    HW/IP 엔지니어가 실행 요청
            ↓
    API가 요청 접수
            ↓
    queue가 오래 걸리는 작업 전달
            ↓
    EDA 작업 실행
            ↓
    log/report/result 생성
            ↓
    Python parser가 구조화
            ↓
    RDB에 실행·조건·측정값 저장
            ↓
    API가 결과 제공
            ↓
    Pub/Sub으로 진행 상태 알림

이 그림은 회사 내부 아키텍처의 공개 사실이 아니라 JD를 이해하기 위한 단순화다.

최소 데이터 모델:

    Run: run_id, design_id, stage, started_at, finished_at, execution_status
    Artifact: artifact_id, run_id, file_type, source_path, checksum
    Metric: artifact_id, metric_name, value, unit, corner, check_status

Run의 성공과 Metric의 통과는 별개다.

## 6. 작은 학습 실험

실제 상용 EDA를 실행하지 않고 직접 만든 synthetic report를 파싱한다.

입력 예:

    SYNTHETIC / NOT GENERATED BY AN EDA TOOL
    fixture_format_version=1
    run_id=run-001
    stage=timing
    corner=SS_0C
    tool_exit_code=0
    worst_slack=-80 ps

출력 목표:

    source_kind=synthetic
    run_id=run-001
    job_status=SUCCEEDED
    parse_status=OK
    timing_status=FAIL
    worst_slack_ns=-0.08
    original_unit=ps

반드시 구분할 상태:

| 상태 | 의미 |
|---|---|
| job_status | 도구 실행 자체가 끝났는가 |
| parse_status | parser가 입력을 읽었는가 |
| timing_status | 해당 timing 검사 기준을 통과했는가 |

실험 사례:

1. +0.12 ns: 실행 성공, 파싱 성공, timing PASS
2. -80 ps: -0.08 ns로 변환, timing FAIL
3. slack 누락: 파싱 PARTIAL, timing UNKNOWN
4. 지원하지 않는 단위: INVALID
5. 같은 필드가 두 번 등장: 조용히 덮어쓰지 않고 INVALID
6. 숫자 손상: INVALID

이 실험은 반도체 EDA parser를 만들었다는 뜻이 아니라, 도메인 산출물을 상태·단위·출처와 함께 구조화하는 연습이다.

## 7. 3일 학습 순서

### Day 1 — 회사와 도메인

읽을 것: 퀄리타스 제품 페이지, 현행·과거 SW Engineer 공고, MCU·SoC·MIPI·UCIe 기본 설명.

해야 할 것:

- 회사 제품을 한 문장으로 설명
- MCU→SoC→IP→PHY 관계를 직접 그림
- PCIe/UCIe/MIPI를 세 문장으로 비교
- 핵심 용어 10개를 보지 않고 설명

통과 기준: 회사 업무에 대한 사실과 SW 관점의 추론을 구분해 설명한다.

### Day 2 — EDA 흐름과 산출물

읽을 것: OpenROAD Flow, IDEC EDA 자료, Synopsys 디지털·아날로그 흐름.

해야 할 것:

- 디지털 흐름 그림 작성
- 아날로그/PHY 흐름 그림 작성
- log/report/result 차이 설명
- 정상 종료·파싱 성공·timing FAIL 사례 설명

통과 기준: “작업은 성공했지만 timing 검사는 실패할 수 있다”를 예시와 함께 설명한다.

### Day 3 — SW 연결과 parser

해야 할 것:

- synthetic report 6개 작성
- Python parser 구현
- JSON 출력 검토
- 실패 사례 테스트
- 5분 면접 설명

통과 기준: 누락·단위 오류·중복을 구분하고 실제 EDA 경험이라고 과장하지 않는다.

## 8. 면접용 5분 설명

1. 임베디드에서는 MCU를 사용했지만, 반도체 회사는 SoC 내부에 들어가는 IP를 만든다는 관점으로 확장했다.
2. 인터페이스 IP는 protocol을 처리하는 controller와 실제 신호를 다루는 PHY로 나누어 이해했다.
3. PCIe는 장치 간, UCIe는 패키지 내 칩렛 간, MIPI는 카메라·디스플레이 연결 계열로 구분했다.
4. EDA에서는 RTL·simulation·verification 이후 synthesis·P&R·timing·sign-off가 이어지고, 아날로그/PHY는 회로 simulation과 신호 분석이 추가된다.
5. SW Engineer는 실행을 요청하고, 로그·리포트를 파싱하고, 결과를 DB에 저장하고, 상태를 API나 이벤트로 전달할 수 있다.
6. 이 흐름을 이해하기 위해 실제 EDA가 아닌 synthetic report parser를 만들고 실행 상태·파싱 상태·검사 상태를 분리했다.

마지막에는 이렇게 제한한다.

> 공개 자료 기반의 도메인 학습과 작은 데이터 처리 실험을 했으며, 상용 EDA 운영이나 PHY 설계 경험이 있다고 주장하지 않습니다.

## 9. 자기 점검

- [ ] MCU, SoC, IP의 차이를 설명했다.
- [ ] Controller와 PHY의 차이를 설명했다.
- [ ] PCIe, UCIe, MIPI를 같은 것으로 섞지 않았다.
- [ ] SerDes, eye diagram, BER, equalization을 설명했다.
- [ ] 디지털과 아날로그 EDA 흐름을 구분했다.
- [ ] log/report/result를 구분했다.
- [ ] job 완료와 검사 통과를 분리했다.
- [ ] synthetic 데이터임을 표시했다.
- [ ] JD의 사실과 추론을 구분했다.
- [ ] 5분 설명을 자료 없이 했다.

10개 중 8개 이상이면 다음 단계로 넘어간다. 미달이면 새 주제를 추가하지 말고 해당 항목만 다시 설명한다.

## 조사 기준과 한계

2026-09-23 기준으로 조사했다. 회사 공식 페이지와 공식 채용 공고를 우선했고, EDA 흐름은 OpenROAD·IDEC·Synopsys 공개 자료, 인터페이스 정의는 MIPI·UCIe 공식 자료를 사용했다.

공개 자료만으로는 퀄리타스 내부의 실제 EDA 도구, 큐 구성, DB 스키마, 파일 포맷, 조직별 업무 분장은 확인할 수 없다. 그런 내용은 이 가이드에서 추론으로 표시했으며 면접에서 사실처럼 말하지 않는다.
