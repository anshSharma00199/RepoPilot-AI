export interface ScanJob {
  id: string;
  repository_id: string;
  started_at: string;
  completed_at?: string | null;
  status: "pending" | "running" | "completed" | "failed";
  total_files: number;
  total_directories: number;
  total_size_bytes: number;
  supported_source_files: number;
  test_files: number;
  manifest_files: number;
  skipped_files: number;
  parse_errors: number;
  detected_frameworks: string[];
  detected_manifests: string[];
  error_details?: string | null;
}

export interface Repository {
  id: string;
  name: string;
  original_filename: string;
  upload_size_bytes: number;
  status: "pending" | "analyzing" | "completed" | "failed";
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  latest_scan?: ScanJob | null;
}

export interface RepositoryDetail extends Repository {
  recent_scans: ScanJob[];
}

export interface AstSyntaxError {
  message: string;
  lineno: number | null;
  offset: number | null;
  text: string | null;
}

export interface AstFunction {
  name: string;
  lineno: number;
  is_async: boolean;
  decorators: string[];
  is_test_func: boolean;
}

export interface AstClass {
  name: string;
  lineno: number;
  bases: string[];
  is_test_class: boolean;
}

export interface AstMetadata {
  success?: boolean;
  imports?: string[];
  classes?: AstClass[];
  functions?: AstFunction[];
  test_indicators?: string[];
  has_test_elements?: boolean;
  syntax_error?: AstSyntaxError | null;
  manifest_info?: {
    manifest_type: string;
    data: any;
  };
}

export interface RepositoryFile {
  id: string;
  repository_id: string;
  scan_job_id?: string | null;
  relative_path: string;
  entry_type: "file" | "directory";
  language: string;
  file_size_bytes: number;
  file_hash?: string | null;
  classification:
    | "source_code"
    | "test"
    | "configuration"
    | "documentation"
    | "generated_output"
    | "binary_data"
    | "other";
  status: "inventoried" | "content_analyzed" | "skipped" | "failed";
  skip_reason?: string | null;
  is_test: boolean;
  is_manifest: boolean;
  ast_metadata?: AstMetadata | null;
  created_at: string;
}

export interface FileTreeNode {
  name: string;
  relative_path: string;
  entry_type: "directory" | "file";
  file_id?: string | null;
  language?: string | null;
  classification?: string | null;
  status?: string | null;
  skip_reason?: string | null;
  file_size_bytes: number;
  is_test: boolean;
  is_manifest: boolean;
  has_syntax_error: boolean;
  children: FileTreeNode[];
}

export interface RepositoryFileListResponse {
  total: number;
  page: number;
  page_size: number;
  items: RepositoryFile[];
}

export interface ApiError {
  error_code: string;
  message: string;
  details?: Record<string, any>;
}

export interface TestFailure {
  test_name: string;
  file?: string | null;
  line?: number | null;
  traceback: string;
}

export interface ExecutionJob {
  id: string;
  repository_id: string;
  status: "pending" | "preparing" | "running" | "completed" | "failed" | "timed_out" | "cancelled";
  stage:
    | "queued"
    | "detecting_command"
    | "installing_dependencies"
    | "executing_tests"
    | "capturing_results"
    | "cleanup"
    | "finished";
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  error_type?: "test_failure" | "setup_error" | "syntax_error" | "timeout_error" | "infrastructure_error" | null;
  error_message?: string | null;
  command: string[];
  image_version: string;
  exit_code?: number | null;
  timed_out: boolean;
  tests_total: number;
  tests_passed: number;
  tests_failed: number;
  tests_skipped: number;
  tests_errors: number;
  failures: TestFailure[];
  cpu_limit: number;
  memory_limit: string;
  timeout_seconds: number;
}

export interface ExecutionJobLogs {
  id: string;
  repository_id: string;
  status: string;
  stdout: string;
  stderr: string;
  setup_logs: string;
  stdout_truncated: boolean;
  stderr_truncated: boolean;
}

export interface EvidenceReference {
  file_path: string;
  line_start: number;
  line_end: number;
  description: string;
  snippet: string;
}

export interface DiagnosticReport {
  id: string;
  job_id: string;
  repository_id: string;
  created_at: string;
  updated_at: string;
  reviewed_at?: string | null;
  status: "proposed" | "approved" | "rejected";
  review_notes?: string | null;
  failure_summary: string;
  root_cause_hypothesis: string;
  confidence_score: number;
  confidence_explanation: string;
  is_insufficient_evidence: boolean;
  insufficient_evidence_reason?: string | null;
  supporting_evidence: EvidenceReference[];
  files_inspected: string[];
  unified_diff: string;
  patch_hash?: string | null;
  affected_files: string[];
  patch_validation_status: "valid" | "invalid" | "rejected_security" | "not_proposed";
  patch_validation_errors: string[];
  potential_regression_risks?: string | null;
  recommended_tests?: string | null;
  known_limitations?: string | null;
  llm_provider: string;
  llm_duration_seconds: number;
}

export interface DiagnosticListResponse {
  total: number;
  items: DiagnosticReport[];
}

export interface ValidationRun {
  id: string;
  repository_id: string;
  baseline_job_id: string;
  diagnostic_report_id: string;
  patched_job_id?: string | null;
  created_at: string;
  completed_at?: string | null;
  patch_version: number;
  patch_hash: string;
  workspace_hash: string;
  affected_files: string[];
  verdict: "VALIDATED" | "UNVALIDATED" | "INFRASTRUCTURE_ERROR";
  verdict_reason_code: string;
  verdict_explanation: string;
  target_test_name?: string | null;
  target_test_passed: boolean;
  regression_tests_passed: boolean;
  baseline_tests_total: number;
  baseline_tests_passed: number;
  baseline_tests_failed: number;
  patched_tests_total: number;
  patched_tests_passed: number;
  patched_tests_failed: number;
  patched_tests_errors: number;
  patched_tests_skipped: number;
  duration_seconds: number;
  tests_executed_before: string[];
  tests_executed_after: string[];
  target_tests_resolved: string[];
  new_regressions: string[];
  attempt_number: number;
  max_attempts: number;
  is_retry_budget_exhausted: boolean;
}

export interface ValidationListResponse {
  total: number;
  items: ValidationRun[];
}

export interface FinalEvidenceReport {
  validation_run_id: string;
  repository_id: string;
  repository_name: string;
  baseline_job_id: string;
  patched_job_id?: string | null;
  created_at: string;
  completed_at?: string | null;
  verdict: "VALIDATED" | "UNVALIDATED" | "INFRASTRUCTURE_ERROR";
  verdict_reason_code: string;
  verdict_explanation: string;
  baseline_summary: any;
  patched_summary: any;
  test_comparison: any;
  ai_diagnosis_summary: any;
  patch_summary: any;
  environment_metadata: any;
  limitations_and_caveats: string[];
  retry_history: any[];
}

export interface SkippedFileDetail {
  relative_path: string;
  entry_type: string;
  language: string;
  file_size_bytes: number;
  classification: string;
  skip_reason: string;
}

export interface AstErrorDetail {
  relative_path: string;
  error_message: string;
  lineno?: number | null;
  offset?: number | null;
}

export interface CategoryBreakdown {
  source_code: number;
  test: number;
  configuration: number;
  documentation: number;
  generated_output: number;
  binary_data: number;
  other: number;
}

export interface AnalysisAuditSummary {
  repository_id: string;
  repository_name: string;
  scan_job_id?: string | null;
  scanned_at?: string | null;
  status: string;

  total_discovered_files: number;
  total_discovered_directories: number;
  total_discovered_entries: number;
  files_inventoried: number;
  files_content_analyzed: number;
  content_analysis_coverage_pct: number;

  python_files_total: number;
  ast_parse_successes: number;
  ast_parse_failures: number;
  ast_syntax_errors: AstErrorDetail[];

  category_counts: CategoryBreakdown;
  test_files_count: number;
  configuration_files_count: number;
  manifest_files_count: number;
  detected_frameworks: string[];
  detected_manifests: string[];

  files_excluded_by_policy_count: number;
  excluded_directories: string[];
  files_skipped_limits_or_unsupported_count: number;
  skipped_files: SkippedFileDetail[];

  explicit_analysis_errors_count: number;
  explicit_errors: string[];
}


