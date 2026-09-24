# 대형 parser·DB synthetic benchmark

실행일: 2026-09-24
명령: `PYTHONPATH=src python3 tools/parser_db_benchmark.py`

## 조건

- 약 8.4 MiB synthetic report
- 120,000개 detail line
- streaming parser
- metric row 20,000개
- SQLite batch insert
- stage/corner/metric_name 복합 인덱스
- 동일 집계 query 30회 반복

## 결과

- parse status: `OK`
- streaming parse: 0.023910초
- batch insert: 0.030206초
- query count: 20,000
- query 평균: 0.002619초
- query p95: 0.002848초
- query 최대: 0.002885초

이 수치는 현재 Mac·SQLite·synthetic 데이터에 대한 기준선이다. 실제 EDA report의 문법 다양성, proprietary tool 산출물, PostgreSQL/MySQL 운영 설정, 여러 writer/readers, artifact object storage는 포함하지 않는다. parser benchmark는 전체 파일을 메모리에 올리지 않고 line streaming을 사용한다. DB benchmark는 metric row batch insert와 stage/corner/name 집계를 확인하지만, production schema나 100명 규모 용량을 증명하지 않는다.
