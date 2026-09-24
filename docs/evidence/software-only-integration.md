# 소프트웨어 전용 연동 검증

기준일: 2026-09-24

실제 SDK와 장비가 없는 환경에서 할 수 있는 연동 작업을 분리해 구현했다.

## 구현

- `Trace32SubprocessClient`: 명시된 `t32rem` 실행 파일과 endpoint를 사용해 command를 호출하는 wrapper
- `AardvarkModuleClient`: 설치된 Python binding module의 `open/transfer/close`를 호출하는 wrapper
- SDK 미설치·실행 파일 없음·연결 실패·timeout을 공통 오류로 정규화
- 실제 adapter는 client를 주입받아 lifecycle과 provenance를 유지
- fake client로 호출 순서와 cleanup을 검증

## 검증 결과

테스트 14개 통과.

- Trace32 command argument 구성
- `t32rem` 미설치 오류
- Aardvark open/transfer/close 매핑
- Aardvark binding 미설치 오류
- real adapter의 `source_kind=real`
- timeout·예외 뒤 resource release

## 남은 실제 작업

SDK package 또는 `t32rem`, Aardvark binding과 실제 장비가 제공되면 환경 설정만 추가하고 단일 smoke test를 실행한다. 현재 구현은 vendor SDK를 포함하거나 장비 동작을 주장하지 않는다.
