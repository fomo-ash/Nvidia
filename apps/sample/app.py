"""Small, deliberately faultable HTTP target for the local incident fixture."""

import os
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REQUESTS = Counter()
LOCK = threading.Lock()
ROUTES = {"/readyz", "/healthz", "/api/work"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        failed = os.getenv("FAIL_MODE", "off").lower() == "on"
        if path == "/metrics":
            with LOCK:
                samples = sorted(REQUESTS.items())
            body = (
                "# HELP sample_http_requests_total HTTP requests to the sample app.\n"
                "# TYPE sample_http_requests_total counter\n"
                + "".join(
                    f'sample_http_requests_total{{route="{route}",status_class="{status}"}} {count}\n'
                    for (route, status), count in samples
                )
            ).encode()
            self._reply(200, body, "text/plain; version=0.0.4")
            return
        if path not in ROUTES:
            self._reply(404, b"not found\n")
            return
        status = 500 if failed and path != "/readyz" else 200
        with LOCK:
            REQUESTS[(path, f"{status // 100}xx")] += 1
        self._reply(status, b"fault active\n" if status == 500 else b"ok\n")

    def _reply(self, status, body, content_type="text/plain"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"sample-api: {format % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()
