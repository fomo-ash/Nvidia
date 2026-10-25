"""Small observable fault fixture. No infrastructure or model dependencies."""

import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class SampleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, *, fail_mode=False):
        self.fail_mode = fail_mode
        self.counts = {("/api/work", "2xx"): 0, ("/api/work", "5xx"): 0}
        self.count_lock = threading.Lock()
        super().__init__(address, SampleHandler)


class SampleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlsplit(self.path).path
        if route == "/metrics":
            with self.server.count_lock:
                lines = [
                    "# HELP sample_http_requests_total Sample HTTP requests by route and status class.",
                    "# TYPE sample_http_requests_total counter",
                    *[
                        f'sample_http_requests_total{{route="{path}",status_class="{status}"}} {count}'
                        for (path, status), count in sorted(self.server.counts.items())
                    ],
                ]
            body = ("\n".join(lines) + "\n").encode()
            self._respond(200, body, "text/plain; version=0.0.4; charset=utf-8")
            return
        if route == "/readyz":
            status, payload = 200, {"status": "ready"}
        elif route in {"/api/work", "/healthz"}:
            status = 500 if self.server.fail_mode else 200
            payload = {
                "status": "error" if self.server.fail_mode else "ok",
                "fault": "FAIL_MODE=on" if self.server.fail_mode else None,
            }
        else:
            status, payload = 404, {"status": "not_found"}
        if route == "/api/work":
            with self.server.count_lock:
                self.server.counts[(route, f"{status // 100}xx")] += 1
            print(
                json.dumps(
                    {
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                        "route": route,
                        "status": status,
                        "fail_mode": self.server.fail_mode,
                    }
                ),
                flush=True,
            )
        self._respond(status, json.dumps(payload).encode(), "application/json")

    def _respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main():
    value = os.environ.get("FAIL_MODE", "off")
    if value not in {"on", "off"}:
        raise ValueError("FAIL_MODE must be on or off")
    server = SampleServer(("0.0.0.0", 8080), fail_mode=value == "on")
    print(json.dumps({"event": "started", "fail_mode": server.fail_mode}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
