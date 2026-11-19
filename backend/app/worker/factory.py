from app.config import settings
from app.worker.interface import ExecutionWorker
from app.worker.docker_worker import DockerWorker
from app.worker.fake_worker import FakeWorker
from app.worker.github_actions_worker import GitHubActionsWorker


def get_worker(force_backend: str = None) -> ExecutionWorker:
    """
    Use simulated execution only when explicitly configured.
    Auto mode prefers the real Docker worker and never fabricates test output.
    """
    backend = (force_backend or settings.WORKER_BACKEND).lower()

    if backend == "fake":
        return FakeWorker()
    if backend == "github_actions":
        return GitHubActionsWorker()

    # DockerWorker returns an infrastructure error if Docker is unavailable.
    # Never silently report simulated tests as results from the uploaded repo.
    return DockerWorker()
