"""Deploy one exact commit to a Render web service and wait for the outcome.

Environment:
  RENDER_API_KEY     Render API key (secret)
  RENDER_SERVICE_ID  srv-... id of the web service
  COMMIT_SHA         full SHA of the commit that CI tested
  DEPLOY_TIMEOUT_SECONDS (optional, default 1500), POLL_SECONDS (optional, default 15)
  RENDER_API_BASE    (optional; tests only)

Exits non-zero unless the deploy of COMMIT_SHA becomes live.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.getenv("RENDER_API_BASE", "https://api.render.com/v1").rstrip("/")
SUCCESS = {"live"}
FAILURE = {
    "build_failed",
    "update_failed",
    "pre_deploy_failed",
    "canceled",
    "deactivated",
}


class DeployError(Exception):
    pass


def api(method, path, body=None):
    request = urllib.request.Request(
        API + path,
        method=method,
        headers={
            "Authorization": "Bearer " + os.environ["RENDER_API_KEY"],
            "Accept": "application/json",
            "User-Agent": "daybook-deploy",
        },
    )
    if body is not None:
        request.data = json.dumps(body).encode()
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        raise DeployError(f"{method} {path} failed with HTTP {error.code}: {detail}") from None


def ensure_auto_deploy_off(service_id):
    _, service = api("GET", f"/services/{service_id}")
    trigger = service.get("autoDeployTrigger")
    if trigger not in (None, "off") or service.get("autoDeploy") == "yes":
        raise DeployError(
            "Render auto-deploy is enabled for this service. Turn it off so only "
            "this workflow deploys tested commits."
        )


def commit_of(deploy):
    return ((deploy or {}).get("commit") or {}).get("id", "")


def find_deploy_for_commit(service_id, sha):
    _, items = api("GET", f"/services/{service_id}/deploys?limit=20")
    for item in items or []:
        deploy = item.get("deploy", item)
        if commit_of(deploy) == sha:
            return deploy
    raise DeployError(f"Render accepted the deploy but no deploy for {sha} was found.")


def trigger(service_id, sha):
    _, deploy = api(
        "POST",
        f"/services/{service_id}/deploys",
        {"commitId": sha, "clearCache": "do_not_clear"},
    )
    if not deploy or not deploy.get("id"):
        # Queued behind another deploy: look it up by commit.
        deploy = find_deploy_for_commit(service_id, sha)
    if commit_of(deploy) and commit_of(deploy) != sha:
        raise DeployError(f"Render created a deploy for {commit_of(deploy)}, not {sha}.")
    return deploy["id"]


def wait(service_id, deploy_id, sha, timeout, interval, sleep=time.sleep):
    deadline = time.monotonic() + timeout
    last = None
    while True:
        _, deploy = api("GET", f"/services/{service_id}/deploys/{deploy_id}")
        status = deploy.get("status")
        if status != last:
            print(f"Deploy {deploy_id}: {status}", flush=True)
            last = status
        if commit_of(deploy) and commit_of(deploy) != sha:
            raise DeployError(f"Deploy {deploy_id} is for {commit_of(deploy)}, not {sha}.")
        if status in SUCCESS:
            return
        if status in FAILURE:
            raise DeployError(f"Deploy {deploy_id} ended with status {status}.")
        if time.monotonic() >= deadline:
            raise DeployError(f"Deploy {deploy_id} still {status} after {timeout} seconds.")
        sleep(interval)


def main():
    service_id = os.environ["RENDER_SERVICE_ID"]
    sha = os.environ["COMMIT_SHA"]
    if len(sha) != 40:
        raise DeployError("COMMIT_SHA must be a full 40-character commit SHA.")
    ensure_auto_deploy_off(service_id)
    deploy_id = trigger(service_id, sha)
    print(f"Triggered deploy {deploy_id} for {sha}", flush=True)
    wait(
        service_id,
        deploy_id,
        sha,
        int(os.getenv("DEPLOY_TIMEOUT_SECONDS", "1500")),
        int(os.getenv("POLL_SECONDS", "15")),
    )
    print(f"Commit {sha} is live.")


if __name__ == "__main__":
    try:
        main()
    except DeployError as error:
        print("::error::" + str(error))
        sys.exit(1)
