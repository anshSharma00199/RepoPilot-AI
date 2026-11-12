import hashlib
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from app.config import settings
from app.services.patch_validator import validate_proposed_patch, PatchValidationResult


class PatchApplicationError(Exception):
    """Raised when patch application fails or security verification rejects the change."""
    pass


def compute_workspace_hash(workspace_dir: Path) -> str:
    """
    Computes a deterministic cryptographic SHA-256 hash across all files in workspace_dir.
    Traverses files in sorted order, hashing relative paths and file bytes.
    """
    hasher = hashlib.sha256()
    workspace_path = workspace_dir.resolve()

    if not workspace_path.exists():
        return hasher.hexdigest()

    all_files = []
    for root, dirs, files in os.walk(workspace_path):
        # Exclude temporary and cache directories
        dirs[:] = [d for d in dirs if d not in settings.DEFAULT_EXCLUDED_DIRS]
        for f in files:
            full_path = Path(root) / f
            try:
                rel_path = full_path.relative_to(workspace_path).as_posix()
                all_files.append((rel_path, full_path))
            except ValueError:
                continue

    # Sort deterministically
    all_files.sort(key=lambda x: x[0])

    for rel_path, full_path in all_files:
        hasher.update(rel_path.encode("utf-8"))
        try:
            content = full_path.read_bytes()
            hasher.update(content)
        except Exception:
            pass

    return hasher.hexdigest()


def create_isolated_snapshot(source_dir: Path, snapshot_id: str) -> Path:
    """
    Creates a new, isolated candidate snapshot directory copy of the repository.
    Guarantees that the canonical upload and baseline snapshot are strictly preserved.
    """
    target_dir = settings.snapshots_path / snapshot_id
    target_dir.mkdir(parents=True, exist_ok=True)

    if source_dir.exists():
        def ignore_patterns(path, names):
            return [n for n in names if n in settings.DEFAULT_EXCLUDED_DIRS]

        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True, ignore=ignore_patterns)

    return target_dir


def cleanup_snapshot(snapshot_id: str) -> None:
    """Removes a snapshot directory when no longer needed."""
    target_dir = settings.snapshots_path / snapshot_id
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)


def apply_approved_patch_to_snapshot(
    snapshot_dir: Path,
    unified_diff: str,
    eligible_files: List[str],
    expected_patch_hash: Optional[str] = None,
) -> Tuple[bool, List[str], str]:
    """
    Applies an approved patch to the isolated working snapshot.
    Enforces:
    1. Validation of diff hunks and non-executing AST syntax parse on modified files.
    2. Verification of patch SHA-256 hash against expected approved hash.
    3. Safe writing only to approved, inventoried files inside the snapshot directory.
    4. Computation of the resulting workspace cryptographic hash.

    Returns:
        (success: bool, affected_files: List[str], workspace_hash: str)
    Raises:
        PatchApplicationError if validation fails or hash mismatch is detected.
    """
    snapshot_path = snapshot_dir.resolve()
    if not snapshot_path.exists():
        raise PatchApplicationError(f"Snapshot directory '{snapshot_path}' does not exist.")

    # 1. Run multi-layer validation engine on the candidate snapshot
    val_result: PatchValidationResult = validate_proposed_patch(
        repo_root=snapshot_path,
        unified_diff=unified_diff,
        eligible_files=eligible_files,
    )

    if not val_result.is_valid:
        err_msg = "; ".join(val_result.errors)
        raise PatchApplicationError(f"Patch validation rejected the proposal: {err_msg}")

    # 2. Verify patch hash integrity if expected_patch_hash provided
    if expected_patch_hash and val_result.patch_hash != expected_patch_hash:
        raise PatchApplicationError(
            f"Patch hash tampering detected! Expected {expected_patch_hash}, got {val_result.patch_hash}."
        )

    # 3. Apply the validated file contents to the isolated snapshot
    written_files = []
    for rel_path, content in val_result.patched_files.items():
        # Prevent any path escaping
        clean_rel = rel_path.replace("\\", "/").lstrip("/")
        if ".." in clean_rel:
            raise PatchApplicationError(f"Security violation: path traversal sequence in '{clean_rel}'.")

        if eligible_files:
            eligible_set = {f.replace("\\", "/").strip() for f in eligible_files}
            if clean_rel not in eligible_set:
                raise PatchApplicationError(f"Security violation: target file '{clean_rel}' is not in the repository file inventory.")

        target_file = (snapshot_path / clean_rel).resolve()
        # Verify containment
        if not str(target_file).startswith(str(snapshot_path)):
            raise PatchApplicationError(f"Security violation: target file '{clean_rel}' escapes snapshot boundary.")

        target_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            target_file.write_text(content, encoding="utf-8")
            written_files.append(clean_rel)
        except Exception as e:
            raise PatchApplicationError(f"Failed to write patched file '{clean_rel}': {str(e)}")

    # 4. Compute resulting workspace hash
    workspace_hash = compute_workspace_hash(snapshot_path)

    return True, written_files, workspace_hash
