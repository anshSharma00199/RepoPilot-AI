import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

secret = os.environ.get("RUNNER_CALLBACK_SECRET", "")
if not secret:
    raise SystemExit("Missing RUNNER_CALLBACK_SECRET GitHub Actions secret")
job_id = os.environ["JOB_ID"]
api = os.environ["API_BASE_URL"].rstrip("/")
path = Path(os.environ.get("RESULT_FILE", "runner-result.json"))
if not path.exists():
    body = json.dumps({"job_id": job_id, "exit_code": None, "duration_seconds": 0, "stdout": "", "stderr": "", "error_type": "infrastructure_error", "error_message": "Runner failed before producing a result."}).encode()
else:
    body = path.read_bytes()
signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
req = urllib.request.Request(
    f"{api}/api/v1/runner/jobs/{job_id}/result",
    data=body,
    headers={"Content-Type": "application/json", "X-RepoPilot-Signature": signature, "User-Agent": "RepoPilot-GitHub-Runner"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=20) as response:
        print(response.read().decode("utf-8", "replace"))
except urllib.error.HTTPError as exc:
    raise SystemExit(f"RepoPilot callback failed: HTTP {exc.code}: {exc.read(2000).decode('utf-8', 'replace')}")
