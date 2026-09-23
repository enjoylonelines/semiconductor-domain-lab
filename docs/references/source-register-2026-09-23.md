# 조사 근거 장부
조사일: 2026-09-23 (KST). 아래는 전체 원문 복제가 아닌 확인 내용의 요약이다.

## 판독 기준
- **F (source-derived fact)**: 출처에 명시된 내용. 회사의 제품 설명은 회사 주장이라는 범위에서 사실로 취급한다.
- **I (inference)**: 공개 업무와 일반 개발 흐름을 연결한 추론. 회사 내부 구현·조직·운영 방식으로 단정하지 않는다.
- **S (study simplification)**: 학습용 모델·예문·가상 실험. 실제 회사 데이터가 아니다.
- **U (unverified)**: 날짜, 발음, 사내 운영 등 아직 확인하지 못한 것.
- 확인 방식의 `검색본문`은 검색 도구가 제공한 색인 본문을 읽었다는 뜻이다. 실시간 원문 직접 열람과 구분한다. 접속 실패를 내용 부재로 해석하지 않는다.

## 채용 근거

| ID | 출처·시점·접근 | 확인한 사실 / 한계 |
|---|---|---|
| J0 | 사용자 제공 현행 JD 요약, 2026-09-23 | RESTful API, 메시지 큐, RDB, migration, 운영, CI/CD 및 Python·EDA/IP·테스트 우대. 첨부 원본 파일은 이번 작업에서 열람하지 않았으며 사용자 제공 요약으로 표시. |
| J1 | [잡코리아 SW Engineer 49942177](https://www.jobkorea.co.kr/Recruit/GI_Read/49942177?Oem_Code=C1&PageGbn=ST&sc=225), 검색본문 | 2026-09-07~09-27 모집 표시. 현행 채용 존재·일정 확인용. 이미지형 상세 JD 전체를 확인한 근거는 아님. 직접 열기는 실패. |
| J2 | [원티드 SW Engineer 368416](https://www.wanted.co.kr/wd/368416), 본문 열람 | API, 비동기 메시지, RDB, Redis Pub/Sub, 반도체 로그·리포트 파싱, 컨테이너 운영 및 장기 업무인 migration·리팩토링·CI/CD를 명시. Python 프레임워크와 MySQL/PostgreSQL 확인. 게시일 미표시이므로 9월 JD와 동일 버전이라고 단정하지 않음. |
| J3 | [회사 공식 채용 SW Engineer 212725](https://q-semi.career.greetinghr.com/ko/o/212725), 검색본문, 직접 열기 실패 | 마감 2026-05-10인 과거 공식 JD. J2 업무와 Kafka/Redis, Git/Jenkins, HW 연동 도구를 확인. 반도체/EDA/IP 지식과 테스트 코드 우대. 당시 프레임워크·RDB·컨테이너 경험은 지원자격이므로 현행 요약의 우대사항과 섞지 않음. |
| J4 | [원티드 SW Engineer 217418](https://www.wanted.co.kr/wd/217418), 본문 열람 | HW 요구사항을 반영한 사내 도구, HW 개발자와 소통, 가이드, 업무 자동화, MCU firmware, WEB 개발 명시. 과거 맥락으로 제공된 공고이나 게시 연도는 미확인, 상시채용 표시만 확인. 공고 번호로 연도를 추정하지 않음. |

**판단:** J0/J2/J3은 backend와 반도체 데이터 처리의 연결을 뒷받침한다. J4는 HW 협업과 도구 개발의 맥락을 뒷받침한다. 직무가 언제, 왜 개편되었는지나 현행 팀이 MCU 개발을 계속 맡는지는 U이다. 채용 포털의 AI 요약은 근거에서 제외했다.

## 회사·제품과 표준

| ID | 출처 | 확인한 사실 / 사용 범위 |
|---|---|---|
| C1 | [퀄리타스 공식 한국어 홈페이지](https://q-semi.com/kr), 검색본문 | SERDES PHY, PCIe Gen4~6 PHY, UCIe PHY, MIPI C/D-PHY 등의 제품군. 카메라·디스플레이용 PHY와 controller 결합 서브시스템도 소개. 상세 수치의 독립 검증은 하지 않음. |
| C2 | [공식 High-speed Interconnect IP Portfolio](https://www.q-semi.com/user/hisp/HIPC1000V), 검색본문 | SerDes의 CTLE/DFE와 BIST, PCIe PHY의 equalization·자체 시험, UCIe die-to-die, MIPI PHY/controller를 확인. 각 기술의 학습 관련성 근거. 직접 열기는 실패했으므로 페이지 접근 상태 명시. |
| C3 | [퀄리타스 2026-05-15 분기보고서](https://kind.krx.co.kr/external/2026/05/15/000888/20260515001894/11013.htm), 공시 검색본문 | MIPI, PCIe/SERDES, 디스플레이, UCIe 칩렛 인터페이스 제품군 확인. 투자 판단·최신 매출·시장점유율은 조사 범위 밖. |
| C4 | [퀄리타스 2024-03-12 공시](https://kind.krx.co.kr/external/2024/03/12/000208/20240312000713/00591.htm), 검색본문 | “서데스” 한국어 표기 및 IP 중심 사업 맥락 확인. 과거 기술 현황을 현재 성능으로 재사용하지 않음. |
| T1 | [UCIe Consortium Specifications](https://www.uciexpress.org/specifications), 본문 열람 | 패키지 내 칩렛 연결 규격의 공식 출발점. 표준 최신 버전과 회사가 제품에 표시한 지원 버전을 동일시하지 않음. |
| T2 | [UCIe Consortium Q&A](https://www.uciexpress.org/post/introduction-to-ucie-webinar-q-a-recap), 검색본문 | 데이터 레인 외 clock/valid/track 및 표준·첨단 패키지 구조 차이. 1.0 시기 설명이며 현재 전체 규격에 무조건 일반화하지 않음. |
| T3 | [MIPI Alliance D-PHY](https://www.mipi.org/specifications/d-phy), 본문 열람 | MIPI는 단일 PHY 이름이 아니며 D-PHY는 개별 물리 계층 규격. 카메라/디스플레이 연결 학습의 표준 출처. |
| T4 | [UCIe architecture 연구 논문, IEEE 2022, 대학 제공 사본](https://emlab.uiuc.edu/ece546/appnotes/UCie_Paper.pdf), 검색본문 | forwarded clock 및 source-synchronous 구조 설명. UCIe를 일반적인 장거리 SerDes 링크와 같은 것으로 그리지 않는 근거. |
| T5 | [MathWorks SerDes 설계 문서](https://www.mathworks.com/help/serdes/design-and-simulate-serdes-systems.html), 검색본문 | equalization, CTLE, DFE와 eye 지표의 의미 확인. MATLAB 설치·실행을 뜻하지 않음. |

## EDA 흐름·한국어 용례

| ID | 출처 | 확인한 사실 / 사용 범위 |
|---|---|---|
| E1 | [OpenROAD Flow 공식 문서](https://openroad-flow-scripts.readthedocs.io/en/latest/mainREADME.html), 본문 열람 | 디지털 RTL부터 합성·배치·클록 트리·배선·timing report·물리 검증·최종 레이아웃 흐름. 퀄리타스가 OpenROAD를 사용한다는 근거는 아님. |
| E2 | [OpenROAD Flow Scripts 공식 튜토리얼](https://openroad-flow-scripts.readthedocs.io/en/latest/tutorials/FlowTutorial.html), 검색본문 및 [원본 문서](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/master/docs/tutorials/FlowTutorial.md) 검색본문 | logs/reports/results 디렉터리, worst slack 예시. 버전에 따라 출력이 달라짐을 명시. 공개 파일을 훗날 쓸 경우 정확한 commit·라이선스·경로를 추가 기록. |
| E3 | [Synopsys Analog & Mixed-Signal Design](https://www.synopsys.com/implementation-and-signoff/custom-design-platform.html), 검색본문 | schematic·layout·회로 simulation·기생 성분 추출·물리 검증의 아날로그/혼성 흐름. 디지털 합성/P&R만으로 모든 PHY 설계를 설명하지 않는 근거. |
| K1 | [IDEC EDA Tool 소개](https://www.idec.or.kr/edatool/intro/), 검색본문 | 합성, 시뮬레이션, 검증, RTL, Place & Route, DRC/LVS, STA 등 국내 교육기관에서 실제 사용하는 표기와 도구 역할. |
| K2 | [IDEC 2026 교육 일정](https://www.idec.or.kr/edu/schedule/detail/), 검색본문 | RTL 기반 설계 합성, 로직 설계 시뮬레이션, 타이밍 분석, PnR·검증 등 현업 강사 강좌명으로 교차 확인. 일정 변경 가능. |
| K3 | [삼성반도체·Synopsys 20nm 협업 자료](https://semiconductor.samsung.com/kr/news-events/news/synopsys-announces-critical-milestone-in-20-nm-design-enablement-collaboration-with-samsung-electron/), 검색본문 | “합성”, “배치 및 배선”, “사인오프”, “테이프아웃” 한국어 실사용. 오래된 기술 사례로서 용어 근거에만 사용. |
| K4 | [Siemens Aprisa 고객 사례](https://resources.sw.siemens.com/ko-KR/article-iroc-technologies-tapes-out-aerospace-soc-with-aprisa-place-and-route/), 검색본문 | 배치 및 라우팅, 테이프아웃, 사인오프 용례 교차 확인. |
| K5 | [Intel 한국어 타이밍 분석기](https://www.intel.co.kr/content/www/kr/ko/support/programmable/support-resources/design-examples/quartus/tq-clock.html), 검색본문 | 슬랙, 양수·음수 여유와 setup slack 정의. FPGA 문서의 수치 의미를 학습에 사용하며 ASIC 툴 출력 형식으로 오인하지 않음. |
| K6 | [Keysight 한국어 BERT 과정](https://www.keysight.com/kr/ko/learn/course.receiver-and-bit-error-rate-testing-bert-basics.html), 검색본문 | “아이 다이어그램”, “비트 오류율” 및 수신기 시험 맥락. |
| K7 | [Teledyne LeCroy 한국어 기술 자료](https://ko.teledynelecroy.com/serialdata/jitter.aspx), 검색본문 | “아이 다이어그램”과 지터 분석 호칭 교차 확인. |
| K8 | [TI 한국어 MCU 개요](https://www.ti.com/ko-kr/product-category/microcontrollers-processors/overview.html), 검색본문 | “마이크로컨트롤러(MCU)”와 임베디드 구성요소 맥락. |
| K9 | [삼성반도체 SoC 설명](https://semiconductor.samsung.com/kr/news-events/tech-blog/all-about-exynos-3-a-deeper-look-at-modem-connectivity-and-security-in-telecommunication/), 검색본문 | “SoC(System-on-Chip, 시스템온칩)”과 여러 기능 블록의 집적. |
| K10 | [Siemens 한국어 MIPI 검증 IP](https://www.siemens.com/ko-kr/products/ic/questa-one/verification-ip/mobile/), 검색본문 | “D-파이” 용례 확인. 번역 페이지 한 곳으로 모든 국내 엔지니어의 PHY 발음을 확정할 수는 없음. |

## 2026-09-24 좁은 STA 보고서 검증을 위한 추가 조사

| ID | 출처·접근 | 확인한 내용 / 사용 경계 |
|---|---|---|
| V1 | [OpenSTA 공식 저장소](https://github.com/parallaxsw/OpenSTA), README 본문 | gate-level 정적 타이밍 분석. Verilog netlist·Liberty·SDC 등 입력을 사용한다. 실물 IP/상용 sign-off 재현 근거가 아님. |
| V2 | [OpenSTA 공식 Examples](https://opensta.readthedocs.io/en/latest/Examples/), 검색본문 | 작은 example1 design과 sdf_delays.tcl 경로. 단위는 Liberty와 설정에 의존하므로 report 숫자만 보고 ns로 가정하지 않음. 파일 취득·실행·revision 고정은 아직 미수행. |
| V3 | [OpenSTA 공식 Commands](https://opensta.readthedocs.io/en/latest/Commands/), 본문 | report_checks의 text/JSON 선택지, report_units, report_worst_slack와 report_wns의 구분 확인. 고정할 실제 버전의 기능을 다시 확인해야 하며 latest 문서를 설치된 기능으로 간주하지 않음. |
| V4 | [OpenSTA 공식 ChangeLog](https://opensta.readthedocs.io/en/latest/ChangeLog/), 검색본문 | 출력 옵션/scene 관련 변경 기록이 있어 version·명령·분석 범위 고정이 필요. 복수 버전 구현을 지금 요구하는 것은 아님. |
| V5 | [과거 공식 SW Engineer JD](https://q-semi.career.greetinghr.com/ko/o/212725), 검색본문 재확인, 직접 열기 실패 | 로그/리포트 파싱·데이터 가공 자동화 업무와 테스트 우대. 2026-05-10 마감인 과거 공고이며 현재 지원 일정의 근거로 쓰지 않음. |

V1~V4는 도구·입출력 계약의 비교 기준이다. 해당 회사가 OpenSTA를 사용한다는 뜻이 아니다. V5 때문에 report parsing을 직무 관련 후보로 택할 수 있지만 실제 회사 병목·입력 포맷은 미확인이다.

환경 확인: DevSpace의 실행파일 탐색 호출은 INVALID_ARGUMENT으로 실패했다. 동일 Mac의 로컬 읽기 fallback PATH에서는 yosys/sta/openroad/iverilog/verilator를 찾지 못했고 docker 경로만 확인했다(Darwin arm64). 전체 디스크·컨테이너 이미지·Docker daemon 가용성은 확인하지 않았으므로 “도구 미설치 확정”으로 해석하지 않는다. 도구 선택은 기존 자산/작은 fixture/라이선스·버전과 한 번의 실행 가능성 확인 후 확정한다. 이번에는 설치·이미지 pull·EDA 실행을 하지 않았다.

## 확인하지 못한 것과 대응
- **PHY(피지):** 사용자 예시의 발음을 뒷받침하는 공식 한국어 자료를 찾지 못함. PHY/물리 계층을 기본 표기로 삼고, “파이”는 K10에서 관찰한 호칭으로 표시. 사내 실제 발음은 U.
- 영어 약자의 한글 독음은 문서에 명시되지 않는 경우가 많다. 아래 계획서의 발음 가이드는 편의를 위한 S이며, 한국 현업 빈도 조사 결과가 아니다.
- 정확한 과거 J4 게시연도, 현행 공고의 첨부 원본, 사내 EDA 도구·파일 포맷·큐 전달 보장·DB 구조는 U. 학습 진행을 막는 조건이 아니며 이력서에서 확정적으로 언급하지 않는다.
- 회사 기술 페이지 일부에는 제품군별 표현이 섞여 있다. 세대별 속도·인코딩 암기는 제외하고, 정확한 수치가 필요해질 때 해당 표준과 제품 문서 버전을 대조한다.
- 상세 링크가 막히면 공식 공시·표준기관·벤더 문서로 대체하되 출처 접근 상태를 남긴다. 블로그 한 편으로 용어를 확정하지 않는다.
