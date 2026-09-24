import json
import statistics
import time
from eda_lab.models import JobSpec
from eda_lab.runner import SyntheticTimingAdapter
from eda_lab.service import JobService
from eda_lab.store import Store


class MixedAdapter:
    def __init__(self, artifact_bytes=64 * 1024):
        self.artifact_bytes = artifact_bytes

    def run(self, spec):
        index = int(spec.job_id.rsplit("-", 1)[1])
        if index % 10 == 8:
            return SyntheticTimingAdapter("timeout").run(spec)
        profile = "missing_worst_slack" if index % 10 == 9 else "normal"
        return SyntheticTimingAdapter(profile, artifact_bytes=self.artifact_bytes).run(spec)


def percentile(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))]


def main():
    count = 100
    service = JobService(Store(), max_workers=8, max_attempts=2, resource_slots=2, adapter=MixedAdapter())
    submitted = {}
    for index in range(count):
        job_id = f"mixed-{index}"
        submitted[job_id] = time.perf_counter()
        service.submit(JobSpec(job_id, "design-load", "PCIe", "synthetic-timing", "TT_25C", 0.12, "ns", 0.01))
    latencies = []
    for job_id, started in submitted.items():
        service.futures[job_id].result(timeout=15)
        latencies.append(time.perf_counter() - started)
    results = [service.get(job_id) for job_id in submitted]
    attempts = sum(len(result["attempts"]) for result in results)
    payload = {
        "synthetic": True,
        "jobs": count,
        "workers": 8,
        "resource_slots": 2,
        "artifact_bytes": 64 * 1024,
        "successes": sum(result["status"] == "SUCCEEDED" for result in results),
        "failures": sum(result["status"] != "SUCCEEDED" for result in results),
        "attempts": attempts,
        "latency_seconds": {
            "mean": round(statistics.mean(latencies), 6),
            "p95": round(percentile(latencies, 95), 6),
            "max": round(max(latencies), 6),
        },
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
