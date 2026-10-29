"""Register the developer-captured healthy fixture template with the API.

Requires a running local API and the owned kind fixture. Prints no credentials.
"""

import http.cookiejar
import json
import re
import urllib.request
from uuid import uuid4

import kind_fixture as fixture

API = "http://localhost:8000/api/v1"
ORIGIN = "http://localhost:5173"


def post(opener, path, body, headers=None):
    request = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Origin": ORIGIN, **(headers or {})},
        method="POST",
    )
    with opener.open(request, timeout=10) as response:
        return json.load(response)


def main():
    current = fixture.deployment()
    baseline = fixture.load_baseline(current)
    values = dict(re.findall(
        r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$",
        (fixture.ROOT / ".env").read_text(), re.M,
    ))
    secret = values.get("OPERATOR_SECRET")
    if not secret:
        raise RuntimeError("Configure the local operator secret first")
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    csrf = post(opener, "/session", {"secret": secret})["csrf_token"]
    result = post(opener, "/trusted-baselines", {
        "target_uid": baseline["uid"],
        "template": baseline["template"],
        "template_hash": baseline["template_hash"],
    }, {"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())})
    print("Registered trusted template for UID " + result["target_uid"])
    print("Template SHA-256: " + result["template_hash"])


if __name__ == "__main__":
    main()
