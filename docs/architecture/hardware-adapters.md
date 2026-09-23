# Hardware Adapter 연동 결정

조사일: 2026-09-23

## 결론
Trace32와 Aardvark는 연동 가능성이 높지만, 현재 프로토타입에서 실제 장치 호출을 구현할 단계는 아니다. 둘을 EDA adapter로 취급하지 않고 Hardware Adapter 계층으로 분리한다.

## Trace32

Lauterbach 공식 자료는 TRACE32 PowerView를 외부 시스템에서 Remote API로 제어할 수 있고, PRACTICE 명령 실행, 연결·초기화·종료, 타깃 메모리 접근 API를 제공한다고 설명한다. t32rem은 실행 중인 PowerView에 명령을 보내는 명령줄 도구이며 Remote API를 활성화해야 한다.

적합한 작업:

- 타깃 연결·초기화
- 디버거 명령 실행
- 레지스터·메모리 읽기/쓰기
- PRACTICE 스크립트 실행
- 실행 로그·결과 수집
- 펌웨어 bring-up·보드 상태 확인 작업의 job화

주의:

- TRACE32 PowerView, debug probe, 타깃 보드, 아키텍처별 설정, 라이선스가 필요할 수 있다.
- 원격 명령이 성공했다고 타깃 펌웨어나 하드웨어 검증이 통과한 것은 아니다.
- 장시간 장치 세션을 여러 job이 공유하면 세션 점유·동시 접근·복구 정책이 필요하다.

출처:

- https://www2.lauterbach.com/pdf/api_remote_c.pdf
- https://support.lauterbach.com/kb/articles/how-to-use-the-t32rem-tool
- https://support.lauterbach.com/kb/articles/practice-tutorial

## Aardvark

Total Phase 공식 자료는 Aardvark가 USB를 통해 I²C/SPI 장치와 통신하고 master 또는 slave로 동작하며, Python을 포함한 API 바인딩을 제공한다고 설명한다. API는 I²C·SPI·GPIO 설정, 읽기·쓰기, transaction log 및 오류 상태를 다룬다.

적합한 작업:

- I²C 레지스터 read/write
- SPI transaction 실행
- 보드 초기화·설정값 주입
- EEPROM/Flash 또는 주변 장치 접근
- transaction log 수집
- 보드 테스트 job의 일부 실행

주의:

- USB 장치 점유와 물리적 연결 상태를 관리해야 한다.
- I²C/SPI 주소, SPI mode, bitrate, chip-select, 전압·배선 조건을 job 입력에 포함해야 한다.
- 통신 오류가 장치가 명령을 처리하지 않았다는 뜻인지, 응답이 유실된 것인지 구분해야 한다.
- Aardvark 통신 성공은 보드나 IP가 기능 요구사항을 만족한다는 의미가 아니다.

출처:

- https://www.totalphase.com/aardvark/
- https://blog.totalphase.com/support/articles/200468316-aardvark-i2c-spi-host-adapter-user-manual/
- https://www.totalphase.com/support/articles/200602607-aardvark-i2c-spi-host-adapter-quick-start-guide/

## 공통 Adapter 계약

EDA adapter와 Hardware adapter가 같은 job 시스템에 들어오더라도 장치 계층은 분리한다.

    HardwareJobSpec
    - target_id
    - adapter_type: trace32 | aardvark
    - operation
    - connection_ref
    - timeout
    - requested_resource

    submit(spec) → adapter_job_id
    poll(adapter_job_id) → execution_state
    collect(adapter_job_id) → artifact_manifest
    release(adapter_job_id) → resource_state

결과 상태는 세 층으로 분리한다.

- execution_status: 장치 명령·세션 실행이 끝났는가
- transport_status: API·USB·원격 연결이 성공했는가
- check_status: 읽은 값이나 테스트 결과가 기준을 만족하는가

예:

    execution_status = SUCCEEDED
    transport_status = OK
    check_status = FAIL

이것은 장치 명령은 정상 실행됐지만 읽은 레지스터 값이나 보드 검사가 기준을 벗어났다는 뜻이다.

## 현재 단계에서의 구현 경계

Stage 1에서는 실제 장치를 호출하지 않고 다음만 만든다.

- Trace32Adapter와 AardvarkAdapter의 인터페이스 정의
- SyntheticHardwareAdapter로 성공·timeout·transport error·check fail을 재현
- 장치 작업 결과도 Run·Artifact·Metric 모델로 저장
- 실제 SDK 호출은 Stage 4의 장치 보유·라이선스 확인 이후 구현

Stage 4에서 실제 연동 전 확인할 것:

1. 장치 모델·펌웨어·드라이버·API 버전
2. 라이선스 및 동시 사용 조건
3. 타깃 보드와 물리 연결
4. 한 장치를 한 번에 몇 job이 사용할 수 있는지
5. timeout·재연결·전원 재인가·세션 정리 방법
6. 원문 로그와 측정 결과의 보존 형식
7. 장치 명령 성공과 검증 통과를 판정하는 기준

## 진짜 문제

연동 코드를 작성하는 것보다 더 어려운 문제는 장치를 공유하는 여러 job의 소유권과 복구다. 따라서 Hardware Adapter를 추가할 때는 API 호출보다 먼저 resource lease, exclusive lock, timeout, cancellation, cleanup, audit log를 설계해야 한다.
