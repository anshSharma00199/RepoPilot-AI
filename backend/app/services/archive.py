import shutil
import uuid
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile
from app.config import settings
from app.services.security import safe_extract_archive, SecurityValidationError


async def save_and_extract_upload(upload_file: UploadFile, repo_id: str) -> Tuple[Path, Path, int]:
    """
    Saves an uploaded ZIP file to the uploads directory streaming in chunks while
    enforcing upload-size limits, then safely extracts it into the extracted directory.
    Returns: (zip_path, extracted_dir, upload_size_bytes)
    """
    repo_upload_dir = settings.uploads_path / repo_id
    repo_upload_dir.mkdir(parents=True, exist_ok=True)
    zip_path = repo_upload_dir / "repository.zip"

    total_bytes = 0
    chunk_size = 1024 * 64  # 64 KB

    try:
        with open(zip_path, "wb") as f:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
                    raise SecurityValidationError(
                        error_code="UPLOAD_SIZE_LIMIT_EXCEEDED",
                        message=f"Upload size ({total_bytes} bytes) exceeded maximum allowed limit ({settings.MAX_UPLOAD_SIZE_BYTES} bytes).",
                        details={"max_size": settings.MAX_UPLOAD_SIZE_BYTES},
                    )
                f.write(chunk)

        extracted_dir = settings.extracted_path / repo_id
        extracted_dir.mkdir(parents=True, exist_ok=True)

        # Perform safe extraction with full security validations
        safe_extract_archive(zip_path, extracted_dir)

        return zip_path, extracted_dir, total_bytes

    except Exception:
        # Cleanup incomplete files on error
        if repo_upload_dir.exists():
            shutil.rmtree(repo_upload_dir, ignore_errors=True)
        extracted_dir = settings.extracted_path / repo_id
        if extracted_dir.exists():
            shutil.rmtree(extracted_dir, ignore_errors=True)
        raise


def delete_repository_storage(repo_id: str) -> None:
    """Removes stored archive and extracted files for a repository."""
    upload_dir = settings.uploads_path / repo_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)
    extracted_dir = settings.extracted_path / repo_id
    if extracted_dir.exists():
        shutil.rmtree(extracted_dir, ignore_errors=True)
