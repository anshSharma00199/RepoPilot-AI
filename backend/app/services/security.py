import os
import zipfile
import stat
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import settings


class SecurityValidationError(Exception):
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class MalformedArchiveError(SecurityValidationError):
    pass


class ArchiveBombError(SecurityValidationError):
    pass


class PathTraversalError(SecurityValidationError):
    pass


class UnsafeSymlinkError(SecurityValidationError):
    pass


def validate_archive_safety(zip_path: Path) -> List[zipfile.ZipInfo]:
    """
    Performs comprehensive pre-extraction security inspection on a ZIP archive.
    Rejects:
    - Corrupt or non-ZIP archives.
    - Path traversal attempts (../, absolute paths, drive letters, UNC paths).
    - Unsafe symlinks.
    - Archive bombs (entry count, uncompressed size, single file size, compression ratio).
    """
    if not zip_path.exists():
        raise MalformedArchiveError(
            error_code="ARCHIVE_NOT_FOUND",
            message="Uploaded archive file could not be located.",
        )

    if not zipfile.is_zipfile(zip_path):
        raise MalformedArchiveError(
            error_code="MALFORMED_ZIP",
            message="Uploaded file is not a valid ZIP archive or has a corrupted header.",
        )

    try:
        zf = zipfile.ZipFile(zip_path, "r")
    except Exception as e:
        raise MalformedArchiveError(
            error_code="CORRUPT_ARCHIVE",
            message=f"Failed to open archive: {str(e)}",
        )

    with zf:
        try:
            infolist = zf.infolist()
        except Exception as e:
            raise MalformedArchiveError(
                error_code="CORRUPT_ZIP_DIRECTORY",
                message=f"Failed to read archive central directory: {str(e)}",
            )

        # 1. Entry Count Limit
        total_entries = len(infolist)
        if total_entries > settings.MAX_ARCHIVE_ENTRIES:
            raise ArchiveBombError(
                error_code="ENTRY_LIMIT_EXCEEDED",
                message=f"Archive contains {total_entries} entries, which exceeds the limit of {settings.MAX_ARCHIVE_ENTRIES}.",
                details={"total_entries": total_entries, "max_entries": settings.MAX_ARCHIVE_ENTRIES},
            )

        total_uncompressed_bytes = 0
        total_compressed_bytes = 0

        # Check each member before any extraction
        for member in infolist:
            filename = member.filename

            # 2. Path Traversal & Absolute Path Checks
            # Check for null bytes
            if "\0" in filename:
                raise PathTraversalError(
                    error_code="NULL_BYTE_IN_PATH",
                    message="Archive entry contains null byte in filename.",
                    details={"filename": filename},
                )

            # Normalize path separators
            norm_name = filename.replace("\\", "/")

            # Absolute path check: Unix absolute (/...), Windows drive (C:...), UNC (//...)
            if norm_name.startswith("/") or (len(norm_name) >= 2 and norm_name[1] == ":") or norm_name.startswith("//"):
                raise PathTraversalError(
                    error_code="ABSOLUTE_PATH_DETECTED",
                    message="Archive entry contains an absolute path.",
                    details={"filename": filename},
                )

            # Path traversal component check
            parts = norm_name.split("/")
            if ".." in parts:
                raise PathTraversalError(
                    error_code="PATH_TRAVERSAL_DETECTED",
                    message="Archive entry contains directory traversal components (..).",
                    details={"filename": filename},
                )

            # 3. Symlink Security Check
            # In ZIP format, external_attr >> 16 holds Unix file permissions if created on Unix
            mode = member.external_attr >> 16
            if mode != 0 and stat.S_ISLNK(mode):
                raise UnsafeSymlinkError(
                    error_code="UNSAFE_SYMLINK_DETECTED",
                    message="Archive contains symbolic links which are prohibited for security.",
                    details={"filename": filename},
                )

            # 4. Per-file size check
            if member.file_size > settings.MAX_ARCHIVE_FILE_BYTES:
                raise ArchiveBombError(
                    error_code="FILE_SIZE_LIMIT_EXCEEDED",
                    message=f"Entry '{filename}' expanded size ({member.file_size} bytes) exceeds the maximum allowed per-file size of {settings.MAX_ARCHIVE_FILE_BYTES} bytes.",
                    details={"filename": filename, "file_size": member.file_size, "limit": settings.MAX_ARCHIVE_FILE_BYTES},
                )

            total_uncompressed_bytes += member.file_size
            total_compressed_bytes += member.compress_size

        # 5. Total expanded size limit
        if total_uncompressed_bytes > settings.MAX_ARCHIVE_EXPANDED_BYTES:
            raise ArchiveBombError(
                error_code="EXPANDED_SIZE_EXCEEDED",
                message=f"Total expanded archive size ({total_uncompressed_bytes} bytes) exceeds limit of {settings.MAX_ARCHIVE_EXPANDED_BYTES} bytes.",
                details={"expanded_bytes": total_uncompressed_bytes, "limit": settings.MAX_ARCHIVE_EXPANDED_BYTES},
            )

        # 6. Compression ratio limit (Zip bomb prevention)
        effective_compressed = max(total_compressed_bytes, 1024)  # Avoid division by near-zero for tiny files
        ratio = total_uncompressed_bytes / effective_compressed
        if ratio > settings.MAX_COMPRESSION_RATIO and total_uncompressed_bytes > (5 * 1024 * 1024):
            raise ArchiveBombError(
                error_code="COMPRESSION_RATIO_EXCEEDED",
                message=f"Archive compression ratio ({ratio:.1f}:1) exceeds the maximum safety threshold of {settings.MAX_COMPRESSION_RATIO}:1.",
                details={"ratio": round(ratio, 2), "max_ratio": settings.MAX_COMPRESSION_RATIO},
            )

        return infolist


def safe_extract_archive(zip_path: Path, destination_dir: Path) -> Path:
    """
    Safely extracts an inspected archive into destination_dir member-by-member.
    Verifies that every target path stays strictly inside destination_dir.
    Guards against decompression bombs by tracking total bytes written on disk.
    """
    destination_dir = destination_dir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)

    validate_archive_safety(zip_path)

    bytes_written_total = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Skip empty filenames
            if not member.filename:
                continue

            # Clean member relative path
            clean_rel = os.path.normpath(member.filename.replace("\\", "/"))
            if clean_rel.startswith(".") or clean_rel.startswith("/") or clean_rel.startswith("\\"):
                # Clean up relative prefix
                clean_rel = clean_rel.lstrip("./\\")

            target_path = (destination_dir / clean_rel).resolve()

            # Strict path containment verification
            try:
                target_path.relative_to(destination_dir)
            except ValueError:
                raise PathTraversalError(
                    error_code="PATH_TRAVERSAL_CONTAINMENT_VIOLATION",
                    message="Target path resolved outside the extraction destination.",
                    details={"filename": member.filename},
                )

            # Directory entry
            if member.is_dir() or member.filename.endswith("/") or member.filename.endswith("\\"):
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            # Ensure parent directories exist
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Stream extraction chunk by chunk to prevent memory bloat and enforce size limits
            with zf.open(member, "r") as source, open(target_path, "wb") as target:
                member_bytes = 0
                while True:
                    chunk = source.read(64 * 1024)
                    if not chunk:
                        break
                    member_bytes += len(chunk)
                    bytes_written_total += len(chunk)

                    if member_bytes > settings.MAX_ARCHIVE_FILE_BYTES:
                        raise ArchiveBombError(
                            error_code="STREAM_FILE_SIZE_EXCEEDED",
                            message=f"File exceeded maximum allowed size during extraction: {member.filename}",
                            details={"filename": member.filename},
                        )

                    if bytes_written_total > settings.MAX_ARCHIVE_EXPANDED_BYTES:
                        raise ArchiveBombError(
                            error_code="STREAM_EXPANDED_SIZE_EXCEEDED",
                            message="Total extracted data exceeded maximum archive expansion limit.",
                        )

                    target.write(chunk)

    return destination_dir
