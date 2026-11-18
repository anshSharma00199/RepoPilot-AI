
import hashlib
import os
import shutil
from pathlib import Path
from typing import List, Tuple, Optional

from app.config import settings
from app.services.patch_validator import (
    validate_proposed_patch,
    PatchValidationResult,
)


class PatchApplicationError(Exception):
    """Raised when patch application or security verification fails."""
    pass


def compute_workspace_hash(workspace_dir: Path) -> str:
    """Compute a deterministic SHA-256 hash of workspace files."""
    hasher = hashlib.sha256()
    workspace_path = workspace_dir.resolve()

    if not workspace_path.exists():
        return hasher.hexdigest()

    all_files = []

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [
            d for d in dirs
            if d not in settings.DEFAULT_EXCLUDED_DIRS
        ]

        for filename in files:
            full_path = Path(root) / filename

            if full_path.is_symlink():
                raise PatchApplicationError(
                    f"Symlink encountered while hashing: {full_path}"
                )

            rel_path = full_path.relative_to(workspace_path).as_posix()
            all_files.append((rel_path, full_path))

    all_files.sort(key=lambda item: item[0])

    for rel_path, full_path in all_files:
        hasher.update(rel_path.encode("utf-8"))

        try:
            hasher.update(full_path.read_bytes())
        except OSError as exc:
            raise PatchApplicationError(
                f"Unable to hash file '{rel_path}': {exc}"
            ) from exc

    return hasher.hexdigest()


def create_isolated_snapshot(source_dir: Path, snapshot_id: str) -> Path:
    """Create a fresh isolated snapshot of the repository."""

    if not snapshot_id or Path(snapshot_id).name != snapshot_id:
        raise PatchApplicationError("Invalid snapshot ID.")

    source_path = source_dir.resolve()
    target_dir = (settings.snapshots_path / snapshot_id).resolve()
    snapshots_root = settings.snapshots_path.resolve()

    try:
        target_dir.relative_to(snapshots_root)
    except ValueError:
        raise PatchApplicationError(
            "Snapshot path escapes the snapshots directory."
        )

    if not source_path.is_dir():
        raise PatchApplicationError(
            f"Source repository does not exist: {source_path}"
        )

    if target_dir.exists():
        raise PatchApplicationError(
            f"Snapshot already exists: {target_dir}"
        )

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    def ignore_patterns(path, names):
        return [
            name for name in names
            if name in settings.DEFAULT_EXCLUDED_DIRS
        ]

    shutil.copytree(
        source_path,
        target_dir,
        ignore=ignore_patterns,
    )

    return target_dir


def cleanup_snapshot(snapshot_id: str) -> None:
    """Remove an isolated snapshot."""

    if not snapshot_id or Path(snapshot_id).name != snapshot_id:
        raise PatchApplicationError("Invalid snapshot ID.")

    target_dir = (settings.snapshots_path / snapshot_id).resolve()

    try:
        target_dir.relative_to(settings.snapshots_path.resolve())
    except ValueError:
        raise PatchApplicationError(
            "Snapshot cleanup path escapes snapshots directory."
        )

    if target_dir.exists():
        shutil.rmtree(target_dir)


def apply_approved_patch_to_snapshot(
    snapshot_dir: Path,
    unified_diff: str,
    eligible_files: List[str],
    expected_patch_hash: Optional[str] = None,
) -> Tuple[bool, List[str], str]:

    snapshot_path = snapshot_dir.resolve()

    if not snapshot_path.is_dir():
        raise PatchApplicationError(
            f"Snapshot directory does not exist: {snapshot_path}"
        )

    # 1. Validate the patch completely before writing anything.
    val_result: PatchValidationResult = validate_proposed_patch(
        repo_root=snapshot_path,
        unified_diff=unified_diff,
        eligible_files=eligible_files,
    )

    if not val_result.is_valid:
        raise PatchApplicationError(
            "Patch validation rejected the proposal: "
            + "; ".join(val_result.errors)
        )

    # 2. Verify approved patch integrity.
    if (
        expected_patch_hash is not None
        and val_result.patch_hash != expected_patch_hash
    ):
        raise PatchApplicationError(
            "Patch hash mismatch. The approved patch may have changed."
        )

    # 3. Prepare all changes and verify every destination.
    prepared = {}

    for rel_path, content in val_result.patched_files.items():

        clean_rel = rel_path.replace("\\", "/")

        if (
            not clean_rel
            or clean_rel.startswith("/")
            or ".." in clean_rel.split("/")
        ):
            raise PatchApplicationError(
                f"Invalid patch target: {clean_rel}"
            )

        eligible_set = {
            item.replace("\\", "/").strip()
            for item in eligible_files
        }

        if eligible_files and clean_rel not in eligible_set:
            raise PatchApplicationError(
                f"Target is not eligible: {clean_rel}"
            )

        target_file = (snapshot_path / clean_rel).resolve()

        try:
            target_file.relative_to(snapshot_path)
        except ValueError:
            raise PatchApplicationError(
                f"Target escapes snapshot: {clean_rel}"
            )

        if not target_file.is_file() or target_file.is_symlink():
            raise PatchApplicationError(
                f"Invalid target file: {clean_rel}"
            )

        prepared[target_file] = content

    # 4. Save originals for rollback.
    originals = {}
    written_files = []

    for target_file in prepared:
        originals[target_file] = target_file.read_bytes()

    try:
        for target_file, content in prepared.items():
            target_file.write_text(
                content,
                encoding="utf-8",
            )
            written_files.append(
                target_file.relative_to(snapshot_path).as_posix()
            )

        # Verify resulting workspace.
        workspace_hash = compute_workspace_hash(snapshot_path)

    except Exception as exc:
        # Roll back all modified files.
        rollback_errors = []

        for target_file in reversed(list(prepared.keys())):
            if target_file in originals:
                try:
                    target_file.write_bytes(originals[target_file])
                except OSError as rollback_exc:
                    rollback_errors.append(str(rollback_exc))

        if rollback_errors:
            raise PatchApplicationError(
                f"Patch failed: {exc}. Rollback also failed: "
                + "; ".join(rollback_errors)
            ) from exc

        raise PatchApplicationError(
            f"Patch application failed; original files restored: {exc}"
        ) from exc

    return True, written_files, workspace_hash
