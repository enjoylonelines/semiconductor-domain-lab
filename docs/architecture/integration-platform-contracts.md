# 연동 플랫폼 조사와 계약

기준일: 2026-09-24

이 문서는 실제 장비나 EDA 라이선스가 없는 상태에서도 구현할 수 있도록, 외부 연동을 공통 계약 뒤에 숨기는 설계 기준을 정한다. fixture adapter는 계약을 검증하지만 실제 장비 동작을 증명하지 않는다.

## 조사 결과

### TRACE32

Lauterbach 공식 Remote API는 실행 중인 TRACE32 프로세스에 연결해 명령 실행과 JTAG 대상 접근을 제공한다. `T32_Init`, `T32_Attach`, 명령 실행 계열을 사용하며, `t32rem`은 외부 shell에서 실행 중인 PowerView에 명령을 보내는 도구다. PowerView에서 Remote API를 활성화해야 한다.

- 연결 전제: PowerView 프로세스, Remote API 설정, 디버거/타깃 연결, 대상별 설정과 라이선스
- 입력: 명령 또는 제한된 작업 명세
- 출력: 명령 응답, 오류 코드, 메모리/레지스터/실행 상태, raw log
- 주의: API 명령 성공은 타깃 검증 통과와 다르다. `transport_status`, `execution_status`, `check_status`를 분리한다.
- 공식 자료: [Remote API](https://www2.lauterbach.com/pdf/api_remote_c.pdf), [Python control](https://www2.lauterbach.com/pdf/app_python.pdf), [t32rem](https://support.lauterbach.com/kb/articles/how-to-use-the-t32rem-tool)

### Aardvark

Total Phase 공식 매뉴얼은 Aardvark를 I²C/SPI host adapter로 설명하고 C/Rosetta binding과 Python 사용 경로를 제공한다. 주소·버스 모드·속도·전송 바이트·GPIO 설정과 통신 오류를 다뤄야 한다. API를 사용해 미리 정의된 응답으로 peripheral slave를 시뮬레이션하는 방법도 공식 자료에 설명돼 있다.

- 연결 전제: USB 장치, 드라이버/API, 보드 전원과 배선, I²C 주소 또는 SPI mode/chip-select
- 입력: 버스·주소·속도·읽기/쓰기·payload 명세
- 출력: raw bytes, ACK/NACK·통신 오류, transaction log
- 주의: 통신 성공은 레지스터 값의 의미적 정합성이나 보드 전체 검증 통과와 다르다.
- 공식 자료: [Aardvark manual](https://www.totalphase.com/support/articles/200468316-aardvark-i2c-spi-host-adapter-user-manual/), [Python example](https://www.totalphase.com/support/articles/201158087-using-the-aardvark-with-python-on-64-bit-windows/), [slave simulation](https://www.totalphase.com/blog/2022/02/how-can-i-set-up-the-spi-host-adapter-to-respond-as-a-peripheral-slave-device/)

### EDA tool 실행

EDA tool 자체는 회사·라이선스·버전·스크립트마다 명령과 report 형식이 달라서 TRACE32/Aardvark와 같은 하드웨어 adapter로 취급하지 않는다. `EdaAdapter`는 실행 명령, 작업 디렉터리, 환경/라이선스 전제, stdout/stderr, report artifact, exit code를 표준화한다.

Qualitas 공식 자료가 PCIe Gen4~6 PHY, UCIe 2.0, SERDES, MIPI C/D-PHY와 BIST·loopback·equalization·eye monitor 같은 검증 결과를 다루므로, parser는 특정 결과를 모두 한 번에 해석하지 않고 tool/flow별 parser registry로 확장한다. [Qualitas IP portfolio](https://www.q-semi.com/user/hisp/HIPC1000V), [공식 제품·데모 자료](https://www.q-semi.com/qaview.php)

## 공통 계약

```python
class ExternalAdapter(Protocol):
    def acquire(self, spec: JobSpec) -> Lease: ...
    def execute(self, lease: Lease, spec: JobSpec) -> RawResult: ...
    def collect(self, raw: RawResult) -> ArtifactSet: ...
    def release(self, lease: Lease) -> None: ...
```

모든 adapter는 다음을 보장한다.

1. `acquire` 성공 전에는 외부 명령이나 USB transaction을 실행하지 않는다.
2. `Lease`는 만료 시간, resource key, owner/job id를 가진다.
3. 모든 호출은 timeout과 cancellation 정책을 명시한다.
4. `release`는 성공·실패·예외에서 모두 시도한다.
5. raw 결과를 보존하고 정규화 결과와 연결한다.
6. 결과에는 `source_kind=fixture|real`, adapter 이름, 버전, 시작/종료 시각, correlation id를 남긴다.
7. `transport_status`, `execution_status`, `parse_status`, `check_status`를 하나의 성공 boolean으로 합치지 않는다.

### 공통 상태

```text
QUEUED
  → ACQUIRING
  → RUNNING
  → COLLECTING
  → PARSING
  → SUCCEEDED | FAILED | CANCELLED | TIMED_OUT
```

`check_status=PASS|FAIL|UNKNOWN`은 실행 상태와 별도다. 예를 들어 TRACE32 명령이 실행됐지만 타깃 assertion이 실패하면 `execution_status=SUCCEEDED`, `check_status=FAIL`이다.

### 공통 오류 분류

- `configuration_error`: 주소·스크립트·필수 설정 오류, 재시도하지 않음
- `resource_unavailable`: 장비·라이선스·slot 부족, bounded backoff 가능
- `transport_error`: USB·TCP·Remote API·버스 통신 오류, 제한 재시도
- `timeout`: acquire/execute/collect 단계별 timeout, 제한 재시도
- `artifact_missing`: 결과 파일 누락, 원인 확인 후 재시도 여부 결정
- `parse_invalid`: 형식·필드·단위 오류, 재시도하지 않음
- `check_failed`: 도구는 정상 실행됐지만 설계/타깃 검증 조건 실패, 재시도하지 않음

## 플랫폼별 계약

### Trace32Adapter

`Trace32JobSpec`은 `powerview_endpoint`, `target_config`, `commands`, `timeout_seconds`, `expected_checks`를 가진다. adapter는 `T32_Init/Attach` 또는 승인된 `t32rem` 호출을 사용하고, 명령별 raw 응답과 target 상태를 저장한다. lease는 PowerView 세션 또는 디버거/타깃 조합을 독점한다.

성공 조건:

- 연결과 명령 실행이 끝남: `transport_status=OK`, `execution_status=SUCCEEDED`
- 기대한 target check가 통과함: `check_status=PASS`

둘 중 하나만 만족하면 전체 성공으로 기록하지 않는다. fixture는 API 응답과 target 상태를 재현할 뿐 실제 JTAG 접근을 검증하지 않는다.

### AardvarkAdapter

`AardvarkJobSpec`은 `device_id`, `bus=I2C|SPI`, `address_or_cs`, `bitrate`, `spi_mode`, `operations`, `timeout_seconds`를 가진다. adapter는 USB 장치를 acquire한 뒤 transaction 단위 raw bytes와 오류를 저장하고 반드시 close/release한다.

성공 조건:

- USB/API transaction이 완료됨: `transport_status=OK`
- 응답 bytes가 명세의 길이·mask·expected value를 만족함: `check_status=PASS`

Aardvark의 master/slave fixture는 protocol-level 테스트에 사용하지만 전압·배선·신호 무결성 검증으로 해석하지 않는다.

### EdaAdapter

`EdaJobSpec`은 `tool_name`, `tool_version`, `flow_name`, `command_template_id`, `workdir_policy`, `license_class`, `timeout_seconds`를 가진다. 임의의 shell 문자열을 API 입력으로 받지 않고 승인된 command template과 parameter schema를 사용한다. stdout/stderr, exit code, report 목록, 파일 hash를 저장한다.

parser는 tool/flow/version별로 선택하고, report parse 성공과 timing/BER/eye/BIST 같은 check 결과를 분리한다. 실제 proprietary report를 fixture로 만들 때는 `source_kind=fixture`를 강제한다.

## Fixture 계약

fixture는 다음 필드를 포함한다.

```json
{
  "source_kind": "fixture",
  "adapter": "trace32|aardvark|eda",
  "profile": "normal|timeout|transport_error|missing_artifact|malformed_result",
  "resource_key": "trace32-target-1",
  "delay_ms": 100,
  "raw_result": {},
  "expected_status": "..."
}
```

fixture 테스트가 증명하는 것:

- 상태 전이, retry, timeout, lease release, parser와 DB 계약

fixture 테스트가 증명하지 않는 것:

- 실제 장비 연결, 전기적 특성, JTAG/I²C/SPI 신호 품질, EDA license checkout, proprietary tool의 실제 report 형식

## Stage 4 진입 조건

- 실제 장비/SDK/드라이버/라이선스 전제 확인
- adapter별 최소 smoke command와 cleanup 확인
- 동일 job의 중복 side effect 방지
- 장비 lease timeout과 장애 시 release 확인
- fixture 결과와 real 결과의 provenance 분리
- real run은 처음부터 1개 장비·1개 IP·1개 flow로 제한
