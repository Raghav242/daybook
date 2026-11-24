"""Smoke-test a running combined production image over HTTP.

Usage: python scripts/smoke_production.py BASE_URL PUBLIC_ORIGIN
  BASE_URL       where the container is reachable, e.g. http://127.0.0.1:10000
  PUBLIC_ORIGIN  the origin the container was configured with in CORS_ORIGINS

Only for disposable test databases: it registers a throwaway account.
Cookies are handled by hand because the image sets Secure cookies, which an
HTTP client would otherwise refuse to send back over plain HTTP.
"""

import json
import re
import secrets
import sys
import time
import urllib.error
import urllib.request

BASE, ORIGIN = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
cookies = {}


def call(method, path, body=None, headers=None):
    request = urllib.request.Request(BASE + path, method=method, headers=dict(headers or {}))
    if body is not None:
        request.data = json.dumps(body).encode()
        request.add_header("Content-Type", "application/json")
    if cookies:
        request.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))
    try:
        response = urllib.request.urlopen(request, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    raw = response.read()
    for header in response.headers.get_all("Set-Cookie") or []:
        name, value = header.split(";", 1)[0].split("=", 1)
        if "max-age=0" in header.lower() or not value.strip('"'):
            cookies.pop(name, None)
        else:
            cookies[name] = value
    return response.status, response.headers, raw


def check(condition, message):
    if not condition:
        raise SystemExit("FAIL: " + message)
    print("ok:", message)


def wait_until_healthy(seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if call("GET", "/api/health")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    raise SystemExit("FAIL: /api/health did not become ready")


wait_until_healthy()

status, headers, raw = call("GET", "/")
html = raw.decode()
check(status == 200 and '<div id="root"' in html, "index.html is served at /")
check(headers["Cache-Control"] == "no-cache", "index.html is revalidated (no-cache)")
status, _, _ = call("GET", "/", headers={"If-None-Match": headers["ETag"]})
check(status == 304, "index.html answers conditional requests with 304")
assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
check(assets, "index.html references built assets")
for asset in assets:
    status, headers, _ = call("GET", asset)
    check(status == 200, f"{asset} is served")
    check("immutable" in headers["Cache-Control"], f"{asset} is cached as immutable")

status, headers, raw = call("GET", "/api/definitely-not-a-route")
check(
    status == 404 and json.loads(raw)["error"]["code"] == "http_error", "unknown /api is a JSON 404"
)
check(headers["Cache-Control"] == "no-store", "API responses are not stored")
check(call("GET", "/settings")[0] == 404, "non-asset paths are not rewritten to the SPA")

status, headers, raw = call("GET", "/api/auth/csrf")
cookie = (headers.get("Set-Cookie") or "").lower()
check(
    status == 200 and "secure" in cookie and "httponly" in cookie,
    "session cookie is Secure+HttpOnly",
)
check("samesite=lax" in cookie, "session cookie is SameSite=Lax")
csrf = json.loads(raw)["csrf_token"]

username = "smoke-" + secrets.token_hex(4)
password = secrets.token_urlsafe(16)
credentials = {"username": username, "password": password}
status, _, _ = call(
    "POST",
    "/api/auth/register",
    credentials,
    {"Origin": "https://evil.example", "X-CSRF-Token": csrf},
)
check(status == 403, "cross-origin registration is rejected")
same_origin = {"Origin": ORIGIN}
status, _, raw = call(
    "POST", "/api/auth/register", credentials, {**same_origin, "X-CSRF-Token": csrf}
)
check(status == 201, "same-origin registration succeeds")
csrf = json.loads(raw)["csrf_token"]

status, _, raw = call("POST", "/api/auth/logout", None, {**same_origin, "X-CSRF-Token": csrf})
check(status == 204, "logout succeeds")
check(call("GET", "/api/auth/me")[0] == 401, "logged-out session is rejected")

csrf = json.loads(call("GET", "/api/auth/csrf")[2])["csrf_token"]
status, _, raw = call("POST", "/api/auth/login", credentials, {**same_origin, "X-CSRF-Token": csrf})
check(status == 200 and json.loads(raw)["user"]["username"] == username, "login succeeds")
csrf = json.loads(raw)["csrf_token"]
check(
    json.loads(call("GET", "/api/auth/me")[2])["user"]["username"] == username, "session is valid"
)

status, _, _ = call(
    "POST", "/api/tasks", {"title": "Smoke test"}, {**same_origin, "X-CSRF-Token": csrf}
)
check(status == 201, "authenticated write reaches the database")
status, _, raw = call("GET", "/api/tasks")
check(status == 200 and json.loads(raw)["total"] == 1, "the write is read back")
print("Production smoke test passed.")
