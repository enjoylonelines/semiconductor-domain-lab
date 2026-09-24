# Stage 3 현실화 부하 측정

실행일: 2026-09-24
명령: `PYTHONPATH=src python3 tools/mixed_load_test.py`

조건:

- 작업 100개
- worker 8개
- synthetic resource slot 2개로 장비 독점 경합 재현
- 정상 작업당 64 KiB artifact
- 작업당 10ms 실행 지연
- 80% 정상, 10% 결측 report, 10% timeout
- timeout은 최대 2회 시도

결과:

- 성공 80개
- 실패 20개
- 총 attempt 110개
- 평균 완료 지연 1.676985초
- p95 완료 지연 2.873756초
- 최대 완료 지연 2.873805초

이 결과는 이전 40개 smoke benchmark보다 현실적인 기준선이다. 특히 worker 8개보다 resource slot 2개가 작아 자원 경합이 지연을 만든다. 그래도 실제 장비·라이선스·네트워크·대형 parser·프로세스 재시작은 포함하지 않으므로 production capacity 증거는 아니다. 다음 Stage 4에서 실제 adapter를 붙일 때 동일한 지표를 수집한다.
