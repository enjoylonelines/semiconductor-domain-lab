# Stage 3 부하 측정 결과

실행일: 2026-09-24
명령: `PYTHONPATH=src python3 tools/load_test.py`

조건:

- synthetic 작업 40개
- worker 4개
- 작업당 실행 지연 10ms
- 단일 프로세스, SQLite, in-process executor

결과:

- 성공 40개, 실패 0개
- 평균 완료 지연: 0.166825초
- p95 완료 지연: 0.358735초
- 최대 완료 지연: 0.358754초

이 측정은 현재 fixture 경로의 대기·저장 동작만 보여준다. 실제 EDA 실행 시간, report 크기, Trace32/Aardvark 장비 lock, 라이선스 대기, 네트워크 queue, 프로세스 재시작은 포함하지 않는다. 따라서 100명 지원 용량의 증거가 아니며, 다음 측정에서는 실패율·retry 비율·artifact 크기·동시 제출률을 변수로 추가해야 한다.
