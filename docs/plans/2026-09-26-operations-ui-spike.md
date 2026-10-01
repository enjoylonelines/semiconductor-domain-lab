# 운영 UI와 공개 Run API: 읽기 계약 검증

- 상태: 구현 중인 분산 실행 시스템의 읽기 계약 검증. 기존 parser/product STOP을 대체하거나 완료했다고 주장하지 않는다.
- 사용자 결정: React 운영 화면을 실제 API와 연결하고, 분산 worker로 확장 가능한 API 경계를 먼저 만든다.
- 문제: 기존 `/jobs/{job_id}`는 저장소 행을 거의 그대로 반환한다. 목록 조회가 없고 lease token·로컬 artifact 경로가 노출될 수 있어 운영 UI의 공개 계약으로 사용할 수 없다.
- Prediction: unrecorded.

## 이번 계약과 구현 범위

| 경로 | 의미 | 이번 구현 |
|---|---|---|
| `GET /runs` | 최신 실행 목록, 상태 필터, cursor pagination | 구현 |
| `GET /runs/{run_id}` | 공개 Run/Attempt 상세 | 구현 |
| `POST /jobs` / `GET /jobs/{id}` | 기존 synthetic/demo 호환 경로 | 유지 |
| `GET /runs/{run_id}/events` | 영속된 실행 이벤트 | 보류 |
| `GET /runs/{run_id}/artifacts` | 접근 제어된 artifact metadata/download URL | 보류 |
| SSE/WebSocket | 새 이벤트 전달 | 보류 |
| cancel/review mutation | 권한·감사 계약이 필요한 변경 | 보류 |

공개 `Run` 응답은 `run_id`, 설계/flow 식별, 실행·파싱·검사·신뢰 상태, 갱신 시각, 제한된 Attempt 정보를 제공한다. `lease_token`, lease 만료, PID, 내부 worker 식별, 로컬 artifact 절대 경로, raw metrics/provenance는 반환하지 않는다.

목록 cursor는 `(updated_at, run_id)` 정렬 경계를 인코딩한다. API는 cursor를 해석하고 Store는 정렬·필터·경계 검색만 수행한다. 새 이벤트가 들어와도 현재 페이지가 갑자기 재정렬되는 것을 막기 위한 목록 조회 경계이며, realtime event stream이 아니다.

## 상태 규칙

- 실행 상태와 parse/check/trust 상태는 독립 필드로 보존한다.
- artifact는 `available` 여부만 공개한다. 파일 접근은 다음 계약에서 별도 권한·서명 URL/다운로드 정책으로 다룬다.
- Attempt는 기록된 status·시각·재시도 분류·오류 요약만 공개한다.
- Event trace를 Attempt/updated_at에서 임의로 만들어 내지 않는다.

## 수용 조건과 STOP

- SQLite Store와 PostgreSQL Store 모두 목록 정렬/상태 필터/cursor 경계를 지원한다.
- API contract test가 목록·상세·민감 필드 비노출·잘못된 cursor를 검증한다.
- React가 `/runs/{id}` 공개 DTO만 사용하고 build가 통과한다.
- 기존 `/jobs` 및 기존 contract/regression 테스트가 통과한다.
- 이 단계 후 event journal/stream/mutation은 별도 문제·결정·검증으로 진행한다.
