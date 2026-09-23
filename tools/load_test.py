import json
import statistics
import time
from eda_lab.models import JobSpec
from eda_lab.service import JobService
from eda_lab.store import Store


def percentile(values, p):
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((p / 100) * len(ordered) + 0.5) - 1))
    return ordered[index]


def main():
    count = 40
    workers = 4
    service = JobService(Store(), max_workers=workers)
    submitted_at = {}
    for index in range(count):
        job_id = f"load-{index}"
        submitted_at[job_id] = time.perf_counter()
        service.submit(JobSpec(job_id, "design-load", "PCIe", "synthetic-timing", "TT_25C", 0.12, "ns", 0.01))
    latencies = []
    for job_id, started in submitted_at.items():
        service.futures[job_id].result(timeout=5)
        latencies.append(time.perf_counter() - started)
    results = [service.get(job_id) for job_id in submitted_at]
    payload = {
        "synthetic": True,
        "jobs": count,
        "workers": workers,
        "successes": sum(item["status"] == "SUCCEEDED" for item in results),
        "failures": sum(item["status"] != "SUCCEEDED" for item in results),
        "latency_seconds": {
            "mean": round(statistics.mean(latencies), 6),
            "p95": round(percentile(latencies, 95), 6),
            "max": round(max(latencies), 6),
        },
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
