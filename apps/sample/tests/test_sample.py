"""HTTP tests for the observable workload and its failure contract."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sample import SampleServer


class SampleTests(unittest.TestCase):
    def exercise(self, fail_mode):
        server = SampleServer(("127.0.0.1", 0), fail_mode=fail_mode)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"

        def request(path):
            try:
                response = urllib.request.urlopen(base + path, timeout=2)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status, response.read().decode()

        return request

    def test_healthy_work_and_zero_error_series(self):
        request = self.exercise(False)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(request("/api/work")[0], 200)
        self.assertEqual(request("/healthz")[0], 200)
        self.assertEqual(request("/readyz")[0], 200)
        metrics = request("/metrics")[1]
        self.assertIn('route="/api/work",status_class="2xx"} 1', metrics)
        self.assertIn('route="/api/work",status_class="5xx"} 0', metrics)

    def test_fault_breaks_work_and_health_but_keeps_pod_ready(self):
        request = self.exercise(True)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(request("/api/work")[0], 500)
        self.assertEqual(request("/healthz")[0], 500)
        self.assertEqual(request("/readyz")[0], 200)
        self.assertIn('route="/api/work",status_class="5xx"} 1', request("/metrics")[1])

    def test_probes_and_unknown_paths_do_not_dilute_work_metrics(self):
        request = self.exercise(False)
        self.assertEqual(request("/healthz")[0], 200)
        self.assertEqual(request("/readyz")[0], 200)
        self.assertEqual(request("/arbitrary-user-path")[0], 404)
        metrics = request("/metrics")[1]
        self.assertNotIn("arbitrary-user-path", metrics)
        self.assertIn('status_class="2xx"} 0', metrics)
        self.assertIn('status_class="5xx"} 0', metrics)
