"""Direct HTTP probe client for target services."""

import time
from typing import Any
import httpx


class ProbeClient:
    async def check_endpoint(self, url: str, timeout: float = 3.0) -> dict[str, Any]:
        """Probe an HTTP endpoint and return response code, latency, and status."""
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                res = await client.get(url)
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                return {
                    "url": url,
                    "status_code": res.status_code,
                    "latency_ms": latency_ms,
                    "is_healthy": res.status_code == 200,
                    "body_snippet": res.text[:200] if res.text else "",
                }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "url": url,
                "status_code": 0,
                "latency_ms": latency_ms,
                "is_healthy": False,
                "error": str(e),
                "body_snippet": "",
            }
