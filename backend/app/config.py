import os
from pathlib import Path
from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "RepoPilot AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    # Database
    DATABASE_URL: str = "sqlite:///./repopilot.db"

    # Storage paths (relative or absolute)
    STORAGE_DIR: str = "./storage"

    # Security & Archive Limits
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024       # 50 MB
    MAX_ARCHIVE_ENTRIES: int = 10000                     # 10,000 entries
    MAX_ARCHIVE_EXPANDED_BYTES: int = 200 * 1024 * 1024  # 200 MB
    MAX_ARCHIVE_FILE_BYTES: int = 25 * 1024 * 1024       # 25 MB
    MAX_COMPRESSION_RATIO: float = 50.0                  # 50:1

    # Analysis Traversal Limits
    MAX_TRAVERSAL_DEPTH: int = 15
    MAX_FILE_COUNT: int = 5000
    MAX_ANALYSIS_FILE_BYTES: int = 2 * 1024 * 1024      # 2 MB per file
    MAX_TOTAL_ANALYSIS_BYTES: int = 50 * 1024 * 1024    # 50 MB total read

    # Excluded directories (always skipped during deep content analysis)
    DEFAULT_EXCLUDED_DIRS: List[str] = [
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        ".eggs",
        ".next",
        ".turbo",
        ".coverage",
        ".idea",
        ".vscode",
    ]

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Execution Worker & Sandbox Settings
    WORKER_BACKEND: str = "auto"                         # "docker", "fake", or "auto"
    DOCKER_BASE_IMAGE: str = "python:3.11-slim"          # Pinned base container image
    EXECUTION_TIMEOUT_SECONDS: int = 60                  # Wall-clock timeout for test execution
    SETUP_TIMEOUT_SECONDS: int = 120                     # Timeout for preparation/dependency install
    EXECUTION_CPU_LIMIT: float = 1.0                     # CPU limit
    EXECUTION_MEMORY_LIMIT: str = "512m"                 # Memory limit
    EXECUTION_PIDS_LIMIT: int = 100                      # PID limit (prevent fork bombs)

    # Remote GitHub-hosted runner (never expose these values to uploaded code)
    GITHUB_ACTIONS_TOKEN: Optional[str] = None
    GITHUB_ACTIONS_REPOSITORY: Optional[str] = None       # owner/repository containing the trusted workflow
    GITHUB_ACTIONS_REF: str = "main"
    RUNNER_CALLBACK_SECRET: Optional[str] = None
    PUBLIC_API_BASE_URL: Optional[str] = None
    GITHUB_RUNNER_WAIT_SECONDS: int = 360
    MAX_LOG_OUTPUT_BYTES: int = 500 * 1024               # 500 KB bounded log limit

    # Day 3 LLM Diagnosis & Patch Settings
    LLM_PROVIDER: str = "auto"                           # "groq", "gemini", "fake", or "auto"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gemini-2.0-flash"                  # Gemini model
    LLM_TIMEOUT_SECONDS: int = 60                        # Provider request timeout
    LLM_MAX_RETRIES: int = 3                             # Max retries for transient errors
    MAX_DIAGNOSTIC_INPUT_CHARS: int = 64000              # Input size bounds (~16k tokens)
    MAX_DIAGNOSTIC_OUTPUT_TOKENS: int = 4096             # Output size bounds
    MAX_PATCH_FILES: int = 5                             # Max modified files per patch
    MAX_PATCH_DIFF_BYTES: int = 50 * 1024                # 50 KB diff limit

    # Day 4 Validation & Verdict Engine Settings
    MAX_PATCH_ATTEMPTS: int = 2                          # Bounded retry budget per job
    VALIDATION_TIMEOUT_SECONDS: int = 60                 # Wall-clock timeout for validation runs
    REQUIRE_REPRODUCED_FAILURE: bool = True              # Invariant: baseline must reproduce failure

    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def uploads_path(self) -> Path:
        p = self.storage_path / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def extracted_path(self) -> Path:
        p = self.storage_path / "extracted"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def workspaces_path(self) -> Path:
        p = self.storage_path / "workspaces"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def patches_path(self) -> Path:
        p = self.storage_path / "patches"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def snapshots_path(self) -> Path:
        p = self.storage_path / "snapshots"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()


