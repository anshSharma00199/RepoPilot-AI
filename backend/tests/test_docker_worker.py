import pytest
import tempfile
from pathlib import Path
from app.worker.docker_worker import DockerWorker
from app.worker.interface import ExecutionConfig


def test_docker_worker_availability_check():
    """
    Verifies that DockerWorker cleanly assesses Docker availability
    without crashing or throwing unhandled exceptions.
    """
    worker = DockerWorker()
    available, reason = worker.is_available()
    assert isinstance(available, bool)
    assert isinstance(reason, str)
    assert len(reason) > 0


@pytest.mark.asyncio
async def test_docker_worker_real_execution():
    """
    Real Docker container execution integration test.
    Executes if Docker daemon is running; cleanly skips with documented diagnostic if not.
    """
    worker = DockerWorker()
    available, reason = worker.is_available()

    if not available:
        pytest.skip(f"Skipping real Docker integration test because Docker is unavailable in this environment: {reason}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        # Create minimal valid pytest test
        (workspace / "tests").mkdir()
        (workspace / "tests" / "test_docker.py").write_text(
            "import os\n"
            "def test_environment():\n"
            "    # Assert non-root execution (UID != 0)\n"
            "    assert os.getuid() != 0\n"
        )
        (workspace / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")


        config = ExecutionConfig(
            job_id="test-docker-real-job",
            repository_id="test-repo",
            workspace_dir=workspace,
            setup_command=[
                "python", "-m", "pip", "install",
                "--target", "/workspace/.test-deps", "pytest"
            ],
            setup_timeout_seconds=120,
            command=[
                "sh", "-c",
                "PYTHONPATH=/workspace/.test-deps python -m pytest -v"
            ],
            timeout_seconds=30,
        )


        res = await worker.execute(config)

        assert res.exit_code == 0
        assert res.status == "completed"
        assert res.tests_passed == 1
        assert res.tests_failed == 0
