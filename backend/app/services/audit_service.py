from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.models.repository_file import RepositoryFile
from app.schemas.audit import (
    AnalysisAuditSummary,
    SkippedFileDetail,
    AstErrorDetail,
    CategoryBreakdown,
)


def generate_analysis_audit(db: Session, repo_id: str) -> AnalysisAuditSummary:
    """
    Computes a comprehensive repository analysis audit and coverage summary.
    Enforces the invariant: Never report 100% content analysis if some files were skipped,
    unsupported, or excluded.
    """
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise ValueError(f"Repository '{repo_id}' not found.")

    latest_scan = (
        db.query(ScanJob)
        .filter(ScanJob.repository_id == repo_id)
        .order_by(desc(ScanJob.started_at))
        .first()
    )

    all_entries = (
        db.query(RepositoryFile)
        .filter(RepositoryFile.repository_id == repo_id)
        .order_by(RepositoryFile.relative_path)
        .all()
    )

    total_files = 0
    total_dirs = 0
    content_analyzed = 0
    python_files = 0
    ast_errors: List[AstErrorDetail] = []
    skipped_files: List[SkippedFileDetail] = []
    excluded_dirs: List[str] = []
    explicit_errors: List[str] = []

    cat_counts = {
        "source_code": 0,
        "test": 0,
        "configuration": 0,
        "documentation": 0,
        "generated_output": 0,
        "binary_data": 0,
        "other": 0,
    }

    test_count = 0
    manifest_count = 0
    config_count = 0

    for item in all_entries:
        if item.entry_type == "directory":
            total_dirs += 1
            if item.status == "skipped":
                excluded_dirs.append(item.relative_path)
            continue

        total_files += 1

        # Classifications
        cls = item.classification if item.classification in cat_counts else "other"
        cat_counts[cls] += 1

        if item.is_test:
            test_count += 1
        if item.is_manifest:
            manifest_count += 1
        if cls == "configuration":
            config_count += 1

        # Status counts
        if item.status == "content_analyzed":
            content_analyzed += 1
        elif item.status == "skipped":
            skipped_files.append(
                SkippedFileDetail(
                    relative_path=item.relative_path,
                    entry_type=item.entry_type,
                    language=item.language,
                    file_size_bytes=item.file_size_bytes,
                    classification=item.classification,
                    skip_reason=item.skip_reason or "Skipped by policy or limits",
                )
            )
        elif item.status == "failed":
            explicit_errors.append(f"{item.relative_path}: {item.skip_reason or 'Analysis failed'}")

        # Python AST parsing stats
        if item.language == "python":
            python_files += 1
            if item.ast_metadata and item.ast_metadata.get("syntax_error"):
                syn = item.ast_metadata["syntax_error"]
                ast_errors.append(
                    AstErrorDetail(
                        relative_path=item.relative_path,
                        error_message=syn.get("message", "Syntax error"),
                        lineno=syn.get("lineno"),
                        offset=syn.get("offset"),
                    )
                )

    # Calculate AST parse successes vs failures
    ast_parse_failures = len(ast_errors)
    # Python files that were analyzed and had no syntax error
    ast_parse_successes = max(0, python_files - ast_parse_failures)

    # Invariant: Never report 100% content analysis if some files were skipped or unsupported
    skipped_count = len(skipped_files)
    excluded_policy_count = len(excluded_dirs)

    if total_files > 0:
        raw_pct = (content_analyzed / total_files) * 100.0
        # If files were skipped, excluded, or failed, cap coverage at 99.0% maximum
        if (skipped_count > 0 or excluded_policy_count > 0 or content_analyzed < total_files) and raw_pct >= 100.0:
            raw_pct = 99.0
        coverage_pct = round(raw_pct, 1)
    else:
        coverage_pct = 0.0

    if repo.error_message:
        explicit_errors.append(f"Repository Error: {repo.error_message}")
    if latest_scan and latest_scan.error_details:
        explicit_errors.append(f"Scan Error: {latest_scan.error_details}")

    return AnalysisAuditSummary(
        repository_id=repo.id,
        repository_name=repo.name,
        scan_job_id=latest_scan.id if latest_scan else None,
        scanned_at=latest_scan.completed_at if latest_scan else repo.created_at,
        status=repo.status,
        total_discovered_files=total_files,
        total_discovered_directories=total_dirs,
        total_discovered_entries=total_files + total_dirs,
        files_inventoried=len(all_entries),
        files_content_analyzed=content_analyzed,
        content_analysis_coverage_pct=coverage_pct,
        python_files_total=python_files,
        ast_parse_successes=ast_parse_successes,
        ast_parse_failures=ast_parse_failures,
        ast_syntax_errors=ast_errors,
        category_counts=CategoryBreakdown(**cat_counts),
        test_files_count=test_count,
        configuration_files_count=config_count,
        manifest_files_count=manifest_count,
        detected_frameworks=latest_scan.detected_frameworks if latest_scan else [],
        detected_manifests=latest_scan.detected_manifests if latest_scan else [],
        files_excluded_by_policy_count=excluded_policy_count,
        excluded_directories=excluded_dirs,
        files_skipped_limits_or_unsupported_count=skipped_count,
        skipped_files=skipped_files,
        explicit_analysis_errors_count=len(explicit_errors),
        explicit_errors=explicit_errors,
    )
