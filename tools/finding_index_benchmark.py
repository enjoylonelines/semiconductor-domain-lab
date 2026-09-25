"""Measure the single finding-query index challenger on a fixed SQLite workload."""

import json
import tempfile
import time
from pathlib import Path

from eda_lab.store import Store


def seed(store: Store, revision_id: str, count: int) -> None:
    store.create_revision(revision_id, "design-a", revision_id, "lib", "sdc", "OpenSTA-3.1", "parser-1")
    store.save_findings(revision_id, [
        (f"{revision_id}-run", f"S{index % 300}", f"E{index}", "clk", "setup", "TT", -0.05 if index % 10 == 0 else 0.1)
        for index in range(count)
    ])


def measure(path: Path, *, create_index_before_ingest: bool, count: int) -> dict:
    store = Store(path)
    if create_index_before_ingest:
        store.create_finding_query_index()
    started = time.perf_counter()
    seed(store, "base", count)
    seed(store, "candidate", count)
    ingest_seconds = time.perf_counter() - started
    store.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    size_before_index = path.stat().st_size
    index_seconds = 0.0
    if not create_index_before_ingest:
        started = time.perf_counter()
        store.create_finding_query_index()
        index_seconds = time.perf_counter() - started
    store.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    store.connection.close()
    return {
        "ingest_seconds": round(ingest_seconds, 6),
        "index_create_seconds": round(index_seconds, 6),
        "database_bytes": path.stat().st_size,
        "database_bytes_before_index": size_before_index,
    }


def main() -> None:
    count = 10_000
    with tempfile.TemporaryDirectory(prefix="eda-finding-index-") as directory:
        root = Path(directory)
        payload = {
            "synthetic": True,
            "findings_per_revision": count,
            "revisions": 2,
            "without_index_then_create": measure(root / "after.sqlite", create_index_before_ingest=False, count=count),
            "with_index_during_ingest": measure(root / "before.sqlite", create_index_before_ingest=True, count=count),
        }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
