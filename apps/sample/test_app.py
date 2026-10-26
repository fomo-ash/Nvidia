"""Exercise the fixture's distinct readiness, health, traffic, and metric behavior."""

import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from app import REQUESTS, Handler


class SampleTest(unittest.TestCase):
    def test_fault_keeps_readiness_up_and_counts_work_errors(self):
        REQUESTS.clear()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def get(path):
            try:
                response = urllib.request.urlopen(base + path, timeout=2)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status, response.read().decode()

        try:
            with patch.dict(os.environ, {"FAIL_MODE": "on"}):
                self.assertEqual(get("/readyz")[0], 200)
                self.assertEqual(get("/healthz")[0], 500)
                self.assertEqual(get("/api/work")[0], 500)
                self.assertIn(
                    'sample_http_requests_total{route="/api/work",status_class="5xx"} 1',
                    get("/metrics")[1],
                )
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
