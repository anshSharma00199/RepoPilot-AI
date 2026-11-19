import {
  Repository,
  RepositoryDetail,
  RepositoryFileListResponse,
  RepositoryFile,
  FileTreeNode,
  ApiError,
  ExecutionJob,
  ExecutionJobLogs,
  DiagnosticReport,
  DiagnosticListResponse,
  ValidationRun,
  ValidationListResponse,
  FinalEvidenceReport,
  AnalysisAuditSummary,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorData: ApiError = {
      error_code: `HTTP_${res.status}`,
      message: res.statusText || "Request failed",
    };
    try {
      const json = await res.json();
      if (json.detail) {
        if (typeof json.detail === "object" && json.detail.message) {
          errorData = json.detail;
        } else if (typeof json.detail === "string") {
          errorData.message = json.detail;
        }
      }
    } catch {
      // Non-JSON response
    }
    throw errorData;
  }
  return res.json() as Promise<T>;
}

export async function checkHealth(): Promise<{ status: string; app: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/health`);
    return await handleResponse<{ status: string; app: string }>(res);
  } catch {
    return { status: "offline", app: "RepoPilot AI" };
  }
}

export async function fetchRepositories(): Promise<{ total: number; items: Repository[] }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/repositories`, { cache: "no-store" });
  return handleResponse<{ total: number; items: Repository[] }>(res);
}

export async function fetchRepository(id: string): Promise<RepositoryDetail> {
  const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${id}`, { cache: "no-store" });
  return handleResponse<RepositoryDetail>(res);
}

export async function fetchRepositoryTree(id: string): Promise<FileTreeNode> {
  const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${id}/tree`, { cache: "no-store" });
  return handleResponse<FileTreeNode>(res);
}

export interface FileFilterQuery {
  classification?: string;
  status?: string;
  language?: string;
  is_test?: boolean;
  is_manifest?: boolean;
  has_syntax_error?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
}

export async function fetchRepositoryFiles(
  id: string,
  filters: FileFilterQuery = {}
): Promise<RepositoryFileListResponse> {
  const params = new URLSearchParams();
  if (filters.classification) params.set("classification", filters.classification);
  if (filters.status) params.set("status", filters.status);
  if (filters.language) params.set("language", filters.language);
  if (filters.is_test !== undefined) params.set("is_test", String(filters.is_test));
  if (filters.is_manifest !== undefined) params.set("is_manifest", String(filters.is_manifest));
  if (filters.has_syntax_error !== undefined) params.set("has_syntax_error", String(filters.has_syntax_error));
  if (filters.search) params.set("search", filters.search);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.page_size) params.set("page_size", String(filters.page_size));

  const url = `${API_BASE_URL}/api/v1/repositories/${id}/files?${params.toString()}`;
  const res = await fetch(url, { cache: "no-store" });
  return handleResponse<RepositoryFileListResponse>(res);
}

export async function fetchFileDetails(repoId: string, fileId: string): Promise<RepositoryFile> {
  const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/files/${fileId}`, {
    cache: "no-store",
  });
  return handleResponse<RepositoryFile>(res);
}

export async function uploadRepository(file: File): Promise<Repository> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/api/v1/repositories/upload`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<Repository>(res);
}

export async function deleteRepository(id: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    await handleResponse(res);
  }
}

export async function startExecutionJob(
  repositoryId: string,
  command?: string[],
  timeoutSeconds?: number
): Promise<ExecutionJob> {
  const body: any = { repository_id: repositoryId };
  if (command && command.length > 0) body.command = command;
  if (timeoutSeconds) body.timeout_seconds = timeoutSeconds;

  const res = await fetch(`${API_BASE_URL}/api/v1/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<ExecutionJob>(res);
}

export async function fetchJob(jobId: string): Promise<ExecutionJob> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}`, { cache: "no-store" });
  return handleResponse<ExecutionJob>(res);
}

export async function fetchJobLogs(jobId: string): Promise<ExecutionJobLogs> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/logs`, { cache: "no-store" });
  return handleResponse<ExecutionJobLogs>(res);
}

export async function fetchRepositoryJobs(repoId: string): Promise<{ total: number; items: ExecutionJob[] }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/jobs`, { cache: "no-store" });
  return handleResponse<{ total: number; items: ExecutionJob[] }>(res);
}

export async function cancelJob(jobId: string): Promise<ExecutionJob> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  return handleResponse<ExecutionJob>(res);
}

export async function triggerDiagnosis(
  jobId: string,
  options: { allow_exploratory?: boolean; custom_instruction?: string } = {}
): Promise<DiagnosticReport> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/diagnose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
  return handleResponse<DiagnosticReport>(res);
}

export async function fetchDiagnostic(id: string): Promise<DiagnosticReport> {
  const res = await fetch(`${API_BASE_URL}/api/v1/diagnostics/${id}`, { cache: "no-store" });
  return handleResponse<DiagnosticReport>(res);
}

export async function fetchJobDiagnostics(jobId: string): Promise<DiagnosticListResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/diagnostics`, { cache: "no-store" });
  return handleResponse<DiagnosticListResponse>(res);
}

export async function fetchRepositoryDiagnostics(repoId: string): Promise<DiagnosticListResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/diagnostics`, { cache: "no-store" });
  return handleResponse<DiagnosticListResponse>(res);
}

export async function approveDiagnostic(id: string, notes?: string): Promise<DiagnosticReport> {
  const res = await fetch(`${API_BASE_URL}/api/v1/diagnostics/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
  return handleResponse<DiagnosticReport>(res);
}

export async function rejectDiagnostic(id: string, reason?: string): Promise<DiagnosticReport> {
  const res = await fetch(`${API_BASE_URL}/api/v1/diagnostics/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  return handleResponse<DiagnosticReport>(res);
}

export async function startPatchValidation(
  diagnosticId: string,
  customCommand?: string[]
): Promise<ValidationRun> {
  const body: any = {};
  if (customCommand && customCommand.length > 0) body.custom_command = customCommand;

  const res = await fetch(`${API_BASE_URL}/api/v1/diagnostics/${diagnosticId}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<ValidationRun>(res);
}

export async function fetchValidationRun(id: string): Promise<ValidationRun> {
  const res = await fetch(`${API_BASE_URL}/api/v1/validations/${id}`, { cache: "no-store" });
  return handleResponse<ValidationRun>(res);
}

export async function fetchJobValidations(jobId: string): Promise<ValidationListResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/validations`, { cache: "no-store" });
  return handleResponse<ValidationListResponse>(res);
}

export async function fetchRepositoryValidations(repoId: string): Promise<ValidationListResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/validations`, { cache: "no-store" });
  return handleResponse<ValidationListResponse>(res);
}

export async function fetchFinalEvidenceReport(validationId: string): Promise<FinalEvidenceReport> {
  const res = await fetch(`${API_BASE_URL}/api/v1/validations/${validationId}/report`, { cache: "no-store" });
  return handleResponse<FinalEvidenceReport>(res);
}

export async function fetchRepositoryAnalysisAudit(repoId: string): Promise<AnalysisAuditSummary> {
  const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/analysis-audit`, { cache: "no-store" });
  return handleResponse<AnalysisAuditSummary>(res);
}


