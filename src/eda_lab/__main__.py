import os
import sys

from .api import create_server, service_from_environment


def postgres_auto_migrate() -> bool:
    return os.environ.get("EDA_POSTGRES_AUTO_MIGRATE", "1") not in {"0", "false", "False"}


def run_migrate() -> None:
    from .postgres_store import PostgresStore
    dsn = os.environ.get("EDA_POSTGRES_DSN")
    if not dsn:
        raise SystemExit("migrate requires EDA_POSTGRES_DSN")
    store = PostgresStore(dsn, migrate=True)
    store.close()


def run_worker() -> None:
    dsn = os.environ.get("EDA_POSTGRES_DSN")
    sta_path = os.environ.get("EDA_OPENSTA_PATH")
    liberty_path = os.environ.get("EDA_OPENSTA_LIBERTY_PATH")
    fixture_dir = os.environ.get("EDA_OPENSTA_FIXTURE_DIR")
    if not all((dsn, sta_path, liberty_path, fixture_dir)):
        raise SystemExit("worker requires EDA_POSTGRES_DSN, EDA_OPENSTA_PATH, EDA_OPENSTA_LIBERTY_PATH, and EDA_OPENSTA_FIXTURE_DIR")
    from .postgres_store import PostgresStore
    from .runner import OpenStaSubprocessAdapter
    from .service import JobService
    from .worker import PostgresWorker
    from .host_agent import HostAgent
    store = PostgresStore(dsn, migrate=postgres_auto_migrate())
    service = JobService(
        store, max_workers=int(os.environ.get("EDA_WORKER_CONCURRENCY", "4")),
        resource_slots=int(os.environ.get("EDA_WORKER_CONCURRENCY", "4")), max_in_flight=int(os.environ.get("EDA_MAX_IN_FLIGHT", "8")),
        worker_id=os.environ.get("EDA_WORKER_ID", "worker"), execution_mode=os.environ.get("EDA_EXECUTION_MODE", "external"),
        adapter=OpenStaSubprocessAdapter(
            sta_path=sta_path,
            liberty_path=liberty_path,
            fixture_dir=fixture_dir,
            script_name=os.environ.get("EDA_OPENSTA_SCRIPT_NAME", "run.tcl"),
            sdc_name=os.environ.get("EDA_OPENSTA_SDC_NAME", "normal.sdc") or None,
            netlist_path=os.environ.get("EDA_OPENSTA_NETLIST_PATH"),
            expected_corner=os.environ.get("EDA_OPENSTA_CORNER") or None,
            timeout_seconds=float(os.environ.get("EDA_OPENSTA_TIMEOUT_SECONDS", "30")),
            work_root=os.environ.get("EDA_OPENSTA_WORK_ROOT"),
        ),
    )
    try:
        concurrency = int(os.environ.get("EDA_WORKER_CONCURRENCY", "4"))
        host_id = os.environ.get("EDA_HOST_ID")
        host_epoch = os.environ.get("EDA_HOST_EPOCH")
        if bool(host_id) != bool(host_epoch):
            raise SystemExit("EDA_HOST_ID and EDA_HOST_EPOCH must be set together")
        worker = (
            HostAgent(store, service, host_id=host_id, host_epoch=host_epoch)
            if host_id else PostgresWorker(store, service)
        )
        if os.environ.get("EDA_WORKER_ONCE") == "1":
            worker.drain(concurrency=concurrency)
        else:
            worker.serve(concurrency=concurrency, poll_seconds=float(os.environ.get("EDA_WORKER_POLL_SECONDS", "0.5")))
    finally:
        service.close()


def run_supervisor() -> None:
    from threading import Event
    from .execution_supervisor import ExecutionSupervisor
    from .postgres_store import PostgresStore
    from .runner import OpenStaSubprocessAdapter
    required = ("EDA_POSTGRES_DSN", "EDA_HOST_ID", "EDA_OPENSTA_PATH", "EDA_OPENSTA_LIBERTY_PATH", "EDA_OPENSTA_FIXTURE_DIR")
    if not all(os.environ.get(name) for name in required):
        raise SystemExit("supervisor requires PostgreSQL, host identity, and OpenSTA paths")
    store = PostgresStore(os.environ["EDA_POSTGRES_DSN"], migrate=postgres_auto_migrate())
    supervisor = ExecutionSupervisor(
        store,
        OpenStaSubprocessAdapter(
            sta_path=os.environ["EDA_OPENSTA_PATH"], liberty_path=os.environ["EDA_OPENSTA_LIBERTY_PATH"],
            fixture_dir=os.environ["EDA_OPENSTA_FIXTURE_DIR"],
            script_name=os.environ.get("EDA_OPENSTA_SCRIPT_NAME", "run.tcl"),
            sdc_name=os.environ.get("EDA_OPENSTA_SDC_NAME", "normal.sdc") or None,
            netlist_path=os.environ.get("EDA_OPENSTA_NETLIST_PATH"),
            expected_corner=os.environ.get("EDA_OPENSTA_CORNER") or None,
            timeout_seconds=float(os.environ.get("EDA_OPENSTA_TIMEOUT_SECONDS", "30")),
            work_root=os.environ.get("EDA_OPENSTA_WORK_ROOT"),
        ),
        host_id=os.environ["EDA_HOST_ID"], supervisor_id=os.environ.get("EDA_SUPERVISOR_ID", os.environ["EDA_HOST_ID"]),
        lease_seconds=float(os.environ.get("EDA_EXECUTION_LEASE_SECONDS", "30")),
    )
    stop = Event()
    try:
        while not stop.is_set():
            if supervisor.run_once() is None:
                stop.wait(float(os.environ.get("EDA_SUPERVISOR_POLL_SECONDS", "0.5")))
    finally:
        store.close()

if __name__ == "__main__":
    if sys.argv[1:] == ["migrate"]:
        run_migrate()
        raise SystemExit(0)
    if sys.argv[1:] == ["worker"]:
        run_worker()
        raise SystemExit(0)
    if sys.argv[1:] == ["supervisor"]:
        run_supervisor()
        raise SystemExit(0)
    service = service_from_environment()
    server = create_server(service=service)
    print("EDA lab API listening on http://127.0.0.1:8080")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.close()
