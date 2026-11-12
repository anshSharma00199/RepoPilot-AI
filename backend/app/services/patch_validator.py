import ast
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from app.config import settings


@dataclass
class PatchValidationResult:
    is_valid: bool
    status: str  # "valid", "invalid", "rejected_security"
    errors: List[str]
    affected_files: List[str]
    patch_hash: str
    clean_diff: str
    patched_files: Dict[str, str] = field(default_factory=dict)


def _compute_patch_hash(diff_text: str) -> str:
    return hashlib.sha256(diff_text.strip().encode("utf-8")).hexdigest()


def extract_affected_files_from_diff(diff_text: str) -> List[str]:
    """
    Parses unified diff headers to discover all files targeted for modification.
    Looks for headers like:
    --- a/path/to/file.py
    +++ b/path/to/file.py
    """
    affected = set()
    for line in diff_text.splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            parts = line[4:].strip().split()
            if parts:
                raw_path = parts[0]
                # Strip git prefixes a/ and b/
                if raw_path.startswith("a/") or raw_path.startswith("b/"):
                    raw_path = raw_path[2:]
                clean = raw_path.replace("\\", "/").strip()
                if clean and clean != "/dev/null":
                    affected.add(clean)
    return sorted(list(affected))


def apply_unified_diff_to_string(original: str, diff_text: str, target_file: str) -> Tuple[bool, str, Optional[str]]:
    """
    Applies unified diff hunks targeting `target_file` to the original string content.
    Returns: (success, patched_content, error_message)
    """
    lines = original.splitlines()
    orig_lines = list(lines)

    # Find the hunk section for this target file
    hunk_regex = re.compile(r"@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@")
    diff_lines = diff_text.splitlines()

    current_file = None
    in_target_diff = False
    hunks = []
    current_hunk = None

    for line in diff_lines:
        if line.startswith("--- ") or line.startswith("+++ "):
            # Flush the previous file's final hunk before switching file headers.
            if current_hunk is not None:
                hunks.append(current_hunk)
                current_hunk = None
            path_part = line[4:].strip().split()[0]
            if path_part.startswith("a/") or path_part.startswith("b/"):
                path_part = path_part[2:]
            path_part = path_part.replace("\\", "/").strip()

            if path_part == target_file:
                in_target_diff = True
            elif line.startswith("--- ") and path_part != target_file:
                in_target_diff = False

        elif in_target_diff and line.startswith("@@"):
            m = hunk_regex.search(line)
            if m:
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = {
                    "orig_start": int(m.group(1)),
                    "orig_count": int(m.group(2)) if m.group(2) else 1,
                    "new_start": int(m.group(3)),
                    "new_count": int(m.group(4)) if m.group(4) else 1,
                    "lines": [],
                }
        elif in_target_diff and current_hunk:
            if line.startswith("+") or line.startswith("-") or line.startswith(" ") or line == "":
                current_hunk["lines"].append(line)

    if current_hunk:
        hunks.append(current_hunk)

    if not hunks:
        # Check if the diff was a direct replacement without hunk headers
        return False, original, f"No parseable unified diff hunks found for '{target_file}'."

    # Apply hunks sequentially from bottom up to preserve line indices
    # Sort hunks in reverse order of orig_start
    sorted_hunks = sorted(hunks, key=lambda h: h["orig_start"], reverse=True)
    working_lines = list(orig_lines)

    for h in sorted_hunks:
        start_idx = h["orig_start"] - 1  # 0-indexed
        count = h["orig_count"]

        # Reconstruct old and new lines from hunk
        old_hunk_lines = [l[1:] for l in h["lines"] if l.startswith("-") or l.startswith(" ")]
        new_hunk_lines = [l[1:] for l in h["lines"] if l.startswith("+") or l.startswith(" ")]

        # Fuzzy match start index if exact index shifted slightly
        match_idx = None
        for offset in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5):
            candidate = start_idx + offset
            if candidate < 0:
                continue
            slice_lines = working_lines[candidate : candidate + len(old_hunk_lines)]
            if slice_lines == old_hunk_lines:
                match_idx = candidate
                break

        if match_idx is None:
            # Fallback: check if old_hunk_lines is substring anywhere in file
            old_block = "\n".join(old_hunk_lines)
            full_text = "\n".join(working_lines)
            if old_block in full_text:
                replaced_text = full_text.replace(old_block, "\n".join(new_hunk_lines), 1)
                working_lines = replaced_text.splitlines()
                continue
            return False, original, f"Hunk context mismatch at line {h['orig_start']}; could not locate original context lines."

        # Replace slice
        working_lines[match_idx : match_idx + len(old_hunk_lines)] = new_hunk_lines

    return True, "\n".join(working_lines) + ("\n" if original.endswith("\n") else ""), None


def validate_proposed_patch(
    repo_root: Path,
    unified_diff: str,
    eligible_files: Optional[List[str]] = None,
) -> PatchValidationResult:
    """
    Comprehensive security and syntax validation of a proposed patch.
    Enforces:
    1. Syntax & format check (valid diff markers).
    2. Absolute path & traversal rejection (../, /etc/..., C:/...).
    3. Confinement strictly inside repository directory.
    4. Modified files must be inventoried eligible source files.
    5. Diff size & affected file count limits.
    6. Non-destructive dry run applying hunks in memory.
    7. Python AST syntax validation on patched output without code execution.
    8. Patch SHA-256 hash generation.
    """
    errors: List[str] = []
    patch_hash = _compute_patch_hash(unified_diff)
    clean_diff = unified_diff.strip()

    if not clean_diff:
        return PatchValidationResult(
            is_valid=False,
            status="invalid",
            errors=["Proposed unified diff is empty."],
            affected_files=[],
            patch_hash=patch_hash,
            clean_diff="",
        )

    # 1. Size bounds
    diff_bytes = len(clean_diff.encode("utf-8"))
    if diff_bytes > settings.MAX_PATCH_DIFF_BYTES:
        return PatchValidationResult(
            is_valid=False,
            status="rejected_security",
            errors=[f"Patch diff size ({diff_bytes} bytes) exceeds safety limit of {settings.MAX_PATCH_DIFF_BYTES} bytes."],
            affected_files=[],
            patch_hash=patch_hash,
            clean_diff=clean_diff,
        )

    # 2. Extract affected files
    affected_files = extract_affected_files_from_diff(clean_diff)
    if not affected_files:
        return PatchValidationResult(
            is_valid=False,
            status="invalid",
            errors=["No valid target file headers (--- a/... +++ b/...) detected in unified diff."],
            affected_files=[],
            patch_hash=patch_hash,
            clean_diff=clean_diff,
        )

    if len(affected_files) > settings.MAX_PATCH_FILES:
        return PatchValidationResult(
            is_valid=False,
            status="rejected_security",
            errors=[f"Patch targets {len(affected_files)} files, which exceeds the limit of {settings.MAX_PATCH_FILES} files per proposal."],
            affected_files=affected_files,
            patch_hash=patch_hash,
            clean_diff=clean_diff,
        )

    # 3. Path Traversal & Security Confinement Checks
    eligible_set = set(eligible_files or [])

    for target in affected_files:
        norm_target = target.replace("\\", "/")

        # Check traversal and absolute path markers
        if ".." in norm_target.split("/") or norm_target.startswith("/") or (len(norm_target) >= 2 and norm_target[1] == ":") or norm_target.startswith("//"):
            return PatchValidationResult(
                is_valid=False,
                status="rejected_security",
                errors=[f"Security violation: path traversal or absolute path detected in patch target '{target}'."],
                affected_files=affected_files,
                patch_hash=patch_hash,
                clean_diff=clean_diff,
            )

        # Check resolution containment
        resolved = (repo_root / norm_target).resolve()
        try:
            resolved.relative_to(repo_root.resolve())
        except ValueError:
            return PatchValidationResult(
                is_valid=False,
                status="rejected_security",
                errors=[f"Security violation: target path '{target}' resolves outside repository root."],
                affected_files=affected_files,
                patch_hash=patch_hash,
                clean_diff=clean_diff,
            )

        # Check that file exists in repository
        if not resolved.exists() or not resolved.is_file():
            return PatchValidationResult(
                is_valid=False,
                status="rejected_security",
                errors=[f"Security violation: target file '{target}' is not in the repository file inventory."],
                affected_files=affected_files,
                patch_hash=patch_hash,
                clean_diff=clean_diff,
            )

        # Check eligibility against repository inventory if provided
        if eligible_set and norm_target not in eligible_set:
            return PatchValidationResult(
                is_valid=False,
                status="rejected_security",
                errors=[
                    f"Security violation: target file '{target}' is not in the repository file inventory.",
                    f"Target file '{target}' is not an eligible source file for modification.",
                ],
                affected_files=affected_files,
                patch_hash=patch_hash,
                clean_diff=clean_diff,
            )

        # Exclude directories like .git or node_modules
        for excluded in settings.DEFAULT_EXCLUDED_DIRS:
            if norm_target.startswith(excluded) or f"/{excluded}/" in f"/{norm_target}/":
                return PatchValidationResult(
                    is_valid=False,
                    status="rejected_security",
                    errors=[f"Security violation: patch attempts to modify excluded system/dependency directory '{excluded}'."],
                    affected_files=affected_files,
                    patch_hash=patch_hash,
                    clean_diff=clean_diff,
                )

    if errors:
        return PatchValidationResult(
            is_valid=False,
            status="invalid",
            errors=errors,
            affected_files=affected_files,
            patch_hash=patch_hash,
            clean_diff=clean_diff,
        )

    # 4. Dry-run Application & Python AST Syntax Validation
    patched_files_map: Dict[str, str] = {}

    for target in affected_files:
        target_path = (repo_root / target).resolve()
        try:
            original_content = target_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            errors.append(f"Failed to read target file '{target}': {str(e)}")
            continue

        success, patched_content, apply_err = apply_unified_diff_to_string(
            original=original_content,
            diff_text=clean_diff,
            target_file=target,
        )

        if not success:
            errors.append(apply_err or f"Failed to apply patch hunks to '{target}'.")
            continue

        patched_files_map[target] = patched_content

        # 5. Non-executing AST Syntax Validation on patched Python code
        if target.endswith(".py") or target.endswith(".pyi"):
            try:
                ast.parse(patched_content, filename=target)
            except SyntaxError as e:
                errors.append(
                    f"Syntax error introduced by patch in '{target}' at line {e.lineno}: {e.msg}"
                )
            except Exception as e:
                errors.append(f"AST parsing exception in patched file '{target}': {str(e)}")

    is_valid = len(errors) == 0
    status_val = "valid" if is_valid else "invalid"

    return PatchValidationResult(
        is_valid=is_valid,
        status=status_val,
        errors=errors,
        affected_files=affected_files,
        patch_hash=patch_hash,
        clean_diff=clean_diff,
        patched_files=patched_files_map,
    )
