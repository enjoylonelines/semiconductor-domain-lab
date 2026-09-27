"""Keep one M1 Host Agent session alive without claiming a Run.

This probe validates container/session/network boundaries. It never claims an
OpenSTA Run and must not be presented as tool-execution evidence.
"""

from __future__ import annotations

import os
from threading import Event

from eda_lab.host_agent import HostAgent
from eda_lab.postgres_store import PostgresStore
from eda_lab.service import JobService


def main() -> None:
    dsn = os.environ["EDA_POSTGRES_DSN"]
    host_id = os.environ["EDA_HOST_ID"]
    host_epoch = os.environ["EDA_HOST_EPOCH"]
    lease_seconds = float(os.environ.get("EDA_AGENT_LEASE_SECONDS", "3"))
    store = PostgresStore(dsn)
    service = JobService(store, max_workers=1, execution_mode="external", lease_seconds=lease_seconds)
    agent = HostAgent(store, service, host_id=host_id, host_epoch=host_epoch)
    try:
        owner = agent.start()
        print(f"host-agent session={owner.session_id} host={owner.host_id} epoch={owner.host_epoch}", flush=True)
        agent.serve(poll_seconds=max(lease_seconds / 3, 0.1), stop=Event())
    finally:
        service.close()


if __name__ == "__main__":
    main()
