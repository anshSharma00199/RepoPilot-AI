import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

job_id = os.environ["JOB_ID"]
image = os.environ["IMAGE"]
if image != "python:3.11-slim":
    raise SystemExit("Unapproved execution image")
command = json.loads(os.environ["COMMAND_JSON"])
setup = json.loads(os.environ.get("SETUP_JSON", "[]"))
timeout = min(max(int(os.environ["TIMEOUT_SECONDS"]), 5), 300)
if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
    raise SystemExit("Invalid test argv")
if not isinstance(setup, list) or not all(isinstance(x, str) for x in setup):
    raise SystemExit("Invalid setup argv")

root = Path("runner-workspace").resolve()
shutil.rmtree(root, ignore_errors=True)
root.mkdir()
os.chmod(root, 0o777)
archive = Path("runner-repository.zip")
archive.write_bytes(base64.b64decode(os.environ["ARCHIVE_B64"], validate=True))
with zipfile.ZipFile(archive) as zf:
    for info in zf.infolist():
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts or info.is_dir() and info.filename.startswith("/"):
            raise SystemExit("Unsafe archive path rejected")
        mode = info.external_attr >> 16
        if mode & 0o170000 == 0o120000:
            raise SystemExit("Symlink entry rejected")
    zf.extractall(root)
archive.unlink(missing_ok=True)
# Container UID 1000 must be able to write dependency and pytest artifacts.
for directory, subdirs, files in os.walk(root):
    os.chmod(directory, 0o777)
    for filename in files:
        os.chmod(Path(directory) / filename, 0o666)

# Do not mount the Docker socket or pass GitHub/API secrets into the container.
# Setup runs as an unprivileged user with network enabled; tests run with no network.
common = [
    "docker", "run", "--rm", "--cpus=1", "--memory=512m", "--pids-limit=100",
    "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=1000:1000",
    "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m",
    "-e", "HOME=/workspace/.repopilot-home",
    "-e", "PYTHONUSERBASE=/workspace/.repopilot-userbase",
    "-e", "PYTHONDONTWRITEBYTECODE=1",
    "-e", "PYTHONPATH=/workspace/.repopilot-deps",
    "-e", "PYTEST_ADDOPTS=-p no:cacheprovider",
    "-v", f"{root}:/workspace:rw", "-w", "/workspace", image,
]
setup_logs = ""
start = time.monotonic()
exit_code = None
stdout = ""
stderr = ""
timed_out = False
error_type = None
error_message = None

try:
    if setup:
        prep_cmd = common.copy()
        prep_cmd[2:2] = ["--network=bridge"]
        prep = subprocess.run(prep_cmd + setup, capture_output=True, text=True, timeout=180)
        setup_logs = (prep.stdout or "") + (prep.stderr or "")
        if prep.returncode != 0:
            exit_code = prep.returncode
            stderr = "Dependency preparation failed.\n" + (prep.stderr or "")
            error_type = "setup_error"
        else:
            run_cmd = common.copy()
            run_cmd[2:2] = ["--network=none"]
            result = subprocess.run(run_cmd + command, capture_output=True, text=True, timeout=timeout)
            exit_code, stdout, stderr = result.returncode, result.stdout, result.stderr
    else:
        run_cmd = common.copy()
        run_cmd[2:2] = ["--network=none"]
        result = subprocess.run(run_cmd + command, capture_output=True, text=True, timeout=timeout)
        exit_code, stdout, stderr = result.returncode, result.stdout, result.stderr
except subprocess.TimeoutExpired as exc:
    timed_out = True
    exit_code = 124
    stdout = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
    stderr = (exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    error_type = "timeout_error"
    error_message = f"Test execution exceeded {timeout} seconds."
except Exception as exc:
    exit_code = None
    error_type = "infrastructure_error"
    error_message = str(exc)

payload = {
    "job_id": job_id,
    "exit_code": exit_code,
    "duration_seconds": round(time.monotonic() - start, 3),
    "stdout": stdout[-450000:],
    "stderr": stderr[-450000:],
    "setup_logs": setup_logs[-100000:],
    "timed_out": timed_out,
    "error_type": error_type,
    "error_message": error_message,
}
Path("runner-result.json").write_text(json.dumps(payload), encoding="utf-8")
