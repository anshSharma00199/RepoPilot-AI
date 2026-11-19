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



def apply_unified_diff_to_string(
    original: str,
    diff_text: str,
    target_file: str,
) -> Tuple[bool, str, Optional[str]]:
    """
    Safely apply unified diff hunks to an existing file.

    Supports:
    - Standard numbered unified diff headers.
    - Bare @@ headers when the old context uniquely identifies
      the location in the original file.

    Ambiguous or malformed patches are rejected.
    """
    original_lines = original.splitlines()
    diff_lines = diff_text.splitlines()

    hunk_regex = re.compile(
        r"^@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@"
    )

    hunks = []
    current_file = None
    in_target_file = False
    current_hunk = None

    def flush_hunk():
        nonlocal current_hunk
        if current_hunk is not None:
            hunks.append(current_hunk)
            current_hunk = None

    for line in diff_lines:
        if line.startswith("--- "):
            flush_hunk()
            path = line[4:].split("\t", 1)[0].strip()
            if path.startswith("a/"):
                path = path[2:]
            current_file = path.replace("\\", "/")
            in_target_file = current_file == target_file
            continue

        if line.startswith("+++ "):
            path = line[4:].split("\t", 1)[0].strip()
            if path.startswith("b/"):
                path = path[2:]
            path = path.replace("\\", "/")

            if path != target_file:
                in_target_file = False
            continue

        if not in_target_file:
            continue

        if line.startswith("@@"):
            flush_hunk()
            match = hunk_regex.match(line)

            if match:
                current_hunk = {
                    "orig_start": int(match.group(1)),
                    "orig_count": (
                        int(match.group(2))
                        if match.group(2) is not None else 1
                    ),
                    "lines": [],
                    "numbered": True,
                }
            elif line.strip() == "@@":
                current_hunk = {
                    "orig_start": None,
                    "orig_count": None,
                    "lines": [],
                    "numbered": False,
                }
            else:
                return (
                    False,
                    original,
                    f"Malformed hunk header in '{target_file}': {line}",
                )
            continue

        if current_hunk is not None:
            if line.startswith((" ", "+", "-")):
                current_hunk["lines"].append(line)
            elif line.startswith("\\ No newline"):
                continue
            else:
                return (
                    False,
                    original,
                    f"Malformed diff line in '{target_file}': {line}",
                )

    flush_hunk()

    if not hunks:
        return (
            False,
            original,
            f"No parseable unified diff hunks found for '{target_file}'.",
        )

    working_lines = list(original_lines)

    # Apply in reverse order so earlier line positions remain stable.
    for hunk in reversed(hunks):
        old_lines = [
            line[1:]
            for line in hunk["lines"]
            if line.startswith((" ", "-"))
        ]

        new_lines = [
            line[1:]
            for line in hunk["lines"]
            if line.startswith((" ", "+"))
        ]

        if not old_lines and not new_lines:
            return False, original, "Empty diff hunk."

        if hunk["numbered"]:
            expected_index = max(0, hunk["orig_start"] - 1)

            if hunk["orig_count"] != len(old_lines):
                return (
                    False,
                    original,
                    "Hunk old-line count does not match its header.",
                )

            candidates = [
                expected_index + offset
                for offset in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5)
            ]
            matches = [
                index
                for index in candidates
                if index >= 0
                and working_lines[index:index + len(old_lines)] == old_lines
            ]

            if len(matches) != 1:
                return (
                    False,
                    original,
                    f"Hunk context is missing or ambiguous near line "
                    f"{hunk['orig_start']}.",
                )

            match_index = matches[0]

        else:
            # Bare @@: only accept uniquely matching old context.
            if not old_lines:
                return (
                    False,
                    original,
                    "Cannot safely locate a bare @@ hunk without old context.",
                )

            matches = []
            search_limit = len(working_lines) - len(old_lines) + 1

            for index in range(max(0, search_limit)):
                if working_lines[index:index + len(old_lines)] == old_lines:
                    matches.append(index)

            if len(matches) != 1:
                return (
                    False,
                    original,
                    f"Bare @@ hunk context for '{target_file}' "
                    f"matched {len(matches)} locations; exactly one is required.",
                )

            match_index = matches[0]

        working_lines[
            match_index:match_index + len(old_lines)
        ] = new_lines

    result = "\n".join(working_lines)

    if original.endswith("\n"):
        result += "\n"

    return True, result, None


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
