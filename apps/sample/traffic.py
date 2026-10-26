"""Generate steady traffic from inside kind so metric windows are measurable."""

import time
import urllib.error
import urllib.request

while True:
    try:
        urllib.request.urlopen("http://sample-api:8080/api/work", timeout=3).close()
    except (urllib.error.HTTPError, OSError):
        pass
    time.sleep(1)
