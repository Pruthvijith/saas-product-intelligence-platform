"""Exercise the actual ASGI server over a loopback TCP connection."""
import json
import os
import socket
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
import uvicorn

from product_intelligence.api import app as APP


def prepare(folder: Path) -> dict:
    return {"PRODUCT_DB": str(folder/"events.sqlite")}


def verify(client: httpx.Client) -> None:
    row = dict(event_id="receipt_1", event_name="signed_up", event_time="2026-10-01T11:00:00Z",
               user_id="user_1", account_id="acct_1")
    first = client.post("/v1/events", json=row)
    duplicate = client.post("/v1/events", json=row)
    conflict = client.post("/v1/events", json=dict(row, user_id="user_2"))
    metric = client.get("/v1/metrics", params={"as_of": "2026-10-10"})
    assert (first.status_code, duplicate.status_code, conflict.status_code,
            metric.status_code) == (202, 202, 422, 200)
    assert duplicate.json()["duplicate"] and metric.json()["activation"]["eligible_users"] == 1
    print(json.dumps(dict(first=first.status_code, retry=duplicate.json(), conflict=conflict.status_code,
                          activation=metric.json()["activation"])))


def main() -> None:
    with TemporaryDirectory() as folder, socket.socket() as listener:
        settings = prepare(Path(folder))
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        port = listener.getsockname()[1]
        with patch.dict(os.environ, settings):
            server = uvicorn.Server(uvicorn.Config(APP, log_level="error"))
            thread = threading.Thread(target=server.run, kwargs={
                                      "sockets": [listener]}, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic()+10
                while not server.started and thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(0.02)
                if not server.started:
                    raise RuntimeError("Server failed to start")
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=5) as client:
                    verify(client)
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("Server failed to stop")


if __name__ == "__main__":
    main()
