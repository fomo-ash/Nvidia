"""Generate two work requests/second; log HTTP failures without stopping."""

import json
import time
import urllib.error
import urllib.request

TARGET = "http://sample-api.fixproof-demo.svc.cluster.local:8080/api/work"


def main():
    while True:
        started = time.monotonic()
        try:
            with urllib.request.urlopen(TARGET, timeout=2) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
        except OSError:
            status = 0
        print(json.dumps({"route": "/api/work", "status": status}), flush=True)
        time.sleep(max(0, 0.5 - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
