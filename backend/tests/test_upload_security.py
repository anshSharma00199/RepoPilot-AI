import io
import pytest
from tests.fixtures.archive_factory import (
    create_malformed_zip,
    create_traversal_zip,
    create_absolute_path_zip,
    create_symlink_zip,
    create_bomb_ratio_zip,
    create_oversized_file_zip,
)


def test_reject_non_zip_extension(client):
    """Verifies that non-ZIP file uploads are immediately rejected."""
    files = {"file": ("malicious.exe", b"MZ\x90\x00", "application/octet-stream")}
    response = client.post("/api/v1/repositories/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error_code"] == "INVALID_FILE_TYPE"


def test_reject_malformed_zip(client):
    """Verifies that corrupt or malformed archives are rejected with structured error."""
    corrupt_bytes = create_malformed_zip()
    files = {"file": ("corrupt.zip", corrupt_bytes, "application/zip")}
    response = client.post("/api/v1/repositories/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error_code"] in ("MALFORMED_ZIP", "CORRUPT_ARCHIVE")


def test_reject_zip_path_traversal(client):
    """Verifies that directory traversal components (..) in archive entries are blocked."""
    traversal_bytes = create_traversal_zip()
    files = {"file": ("traversal.zip", traversal_bytes, "application/zip")}
    response = client.post("/api/v1/repositories/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error_code"] == "PATH_TRAVERSAL_DETECTED"
    assert "traversal" in data["detail"]["message"].lower()


def test_reject_absolute_paths_unix(client):
    """Verifies that archives containing Unix absolute paths (/...) are rejected."""
    abs_bytes = create_absolute_path_zip(unix_style=True)
    files = {"file": ("absolute_unix.zip", abs_bytes, "application/zip")}
    response = client.post("/api/v1/repositories/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error_code"] == "ABSOLUTE_PATH_DETECTED"


def test_reject_absolute_paths_windows(client):
    """Verifies that archives containing Windows drive letter paths (C:/...) are rejected."""
    abs_bytes = create_absolute_path_zip(unix_style=False)
    files = {"file": ("absolute_win.zip", abs_bytes, "application/zip")}
    response = client.post("/api/v1/repositories/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error_code"] == "ABSOLUTE_PATH_DETECTED"


def test_reject_symlink_entries(client):
    """Verifies that archives with symbolic links are rejected to prevent arbitrary read/write."""
    symlink_bytes = create_symlink_zip()
    files = {"file": ("symlink.zip", symlink_bytes, "application/zip")}
    response = client.post("/api/v1/repositories/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error_code"] == "UNSAFE_SYMLINK_DETECTED"


def test_reject_compression_ratio_zip_bomb(client):
    """Verifies that archives with excessive compression ratio (zip bombs) are rejected."""
    bomb_bytes = create_bomb_ratio_zip()
    files = {"file": ("zipbomb.zip", bomb_bytes, "application/zip")}
    response = client.post("/api/v1/repositories/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error_code"] == "COMPRESSION_RATIO_EXCEEDED"


def test_reject_oversized_file_in_archive(client):
    """Verifies that archives declaring files larger than MAX_ARCHIVE_FILE_BYTES are rejected."""
    oversized_bytes = create_oversized_file_zip(30 * 1024 * 1024)
    files = {"file": ("oversized.zip", oversized_bytes, "application/zip")}
    response = client.post("/api/v1/repositories/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error_code"] == "FILE_SIZE_LIMIT_EXCEEDED"
