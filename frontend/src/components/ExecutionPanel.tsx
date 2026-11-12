"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Cpu,
  Layers,
  Terminal,
  StopCircle,
  Copy,
  Check,
  RefreshCw,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Shield,
  FileCode,
  Sparkles,
  ShieldCheck,
} from "lucide-react";
import {
  ExecutionJob,
  ExecutionJobLogs,
  TestFailure,
  DiagnosticReport,
  ValidationRun,
  FinalEvidenceReport,
} from "../lib/types";
import {
  startExecutionJob,
  fetchJob,
  fetchJobLogs,
  fetchRepositoryJobs,
  cancelJob,
  triggerDiagnosis,
  fetchJobDiagnostics,
  startPatchValidation,
  fetchJobValidations,
  fetchFinalEvidenceReport,
} from "../lib/api";
import { DiagnosticReviewModal } from "./DiagnosticReviewModal";
import { FinalReportModal } from "./FinalReportModal";

interface ExecutionPanelProps {
  repositoryId: string;
}

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued in Worker",
  preparing: "Creating Isolated Workspace",
  detecting_command: "Detecting Test Precedence & Manifests",
  installing_dependencies: "Installing Manifest Dependencies",
  executing_tests: "Executing Tests in Sandboxed Container (--network=none)",
  capturing_results: "Sanitizing Logs & Extracting Evidence",
  cleanup: "Cleaning Up Sandbox Resources",
  finished: "Execution Finished",
};

export function ExecutionPanel({ repositoryId }: ExecutionPanelProps) {
  const [activeJob, setActiveJob] = useState<ExecutionJob | null>(null);
  const [jobHistory, setJobHistory] = useState<ExecutionJob[]>([]);
  const [logs, setLogs] = useState<ExecutionJobLogs | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [activeTab, setActiveTab] = useState<"stdout" | "stderr" | "setup">("stdout");
  const [copied, setCopied] = useState(false);
  const [expandedTracebacks, setExpandedTracebacks] = useState<Record<number, boolean>>({});

  // Diagnostic states
  const [diagnostics, setDiagnostics] = useState<DiagnosticReport[]>([]);
  const [activeDiagnostic, setActiveDiagnostic] = useState<DiagnosticReport | null>(null);
  const [isDiagModalOpen, setIsDiagModalOpen] = useState(false);
  const [isDiagnosing, setIsDiagnosing] = useState(false);

  // Validation & Verdict states (Day 4)
  const [validations, setValidations] = useState<ValidationRun[]>([]);
  const [activeValidation, setActiveValidation] = useState<ValidationRun | null>(null);
  const [isFinalReportOpen, setIsFinalReportOpen] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [finalReport, setFinalReport] = useState<FinalEvidenceReport | null>(null);

  // Polling ref
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Load existing jobs on mount
  useEffect(() => {
    loadJobHistory();
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [repositoryId]);

  const loadJobHistory = async () => {
    try {
      const res = await fetchRepositoryJobs(repositoryId);
      setJobHistory(res.items);
      if (res.items.length > 0 && !activeJob) {
        selectJob(res.items[0]);
      }
    } catch (err) {
      console.error("Failed to load jobs", err);
    }
  };

  const loadJobDiagnostics = async (jobId: string) => {
    try {
      const res = await fetchJobDiagnostics(jobId);
      setDiagnostics(res.items);
      if (res.items.length > 0) {
        setActiveDiagnostic(res.items[0]);
      } else {
        setActiveDiagnostic(null);
      }
    } catch (err) {
      console.error("Failed to load diagnostics", err);
    }
  };

  const loadJobValidations = async (jobId: string) => {
    try {
      const res = await fetchJobValidations(jobId);
      setValidations(res.items);
      if (res.items.length > 0) {
        setActiveValidation(res.items[0]);
      } else {
        setActiveValidation(null);
      }
    } catch (err) {
      console.error("Failed to load validations", err);
    }
  };

  const selectJob = async (job: ExecutionJob) => {
    setActiveJob(job);
    try {
      const logData = await fetchJobLogs(job.id);
      setLogs(logData);
    } catch {
      setLogs(null);
    }

    // Expand all tracebacks by default
    const exp: Record<number, boolean> = {};
    job.failures.forEach((_, idx) => (exp[idx] = true));
    setExpandedTracebacks(exp);

    // Load diagnostics and validations for this job
    await Promise.all([
      loadJobDiagnostics(job.id),
      loadJobValidations(job.id),
    ]);
  };

  // Start polling when job is in progress
  useEffect(() => {
    if (!activeJob) return;

    const isRunning = ["pending", "preparing", "running"].includes(activeJob.status);

    if (isRunning) {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);

      pollTimerRef.current = setInterval(async () => {
        try {
          const updated = await fetchJob(activeJob.id);
          setActiveJob(updated);

          if (!["pending", "preparing", "running"].includes(updated.status)) {
            // Job just finished
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            loadJobHistory();
            const logData = await fetchJobLogs(updated.id);
            setLogs(logData);
            loadJobDiagnostics(updated.id);
            loadJobValidations(updated.id);
          }
        } catch (err) {
          console.error("Error polling job", err);
        }
      }, 1500);
    } else {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    }

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [activeJob?.id, activeJob?.status]);

  const handleStartRun = async () => {
    setIsStarting(true);
    try {
      const newJob = await startExecutionJob(repositoryId);
      setActiveJob(newJob);
      setLogs(null);
      await loadJobHistory();
    } catch (err: any) {
      alert(`Failed to start execution: ${err.message || "Unknown error"}`);
    } finally {
      setIsStarting(false);
    }
  };

  const handleCancelRun = async () => {
    if (!activeJob) return;
    setIsCancelling(true);
    try {
      const cancelled = await cancelJob(activeJob.id);
      setActiveJob(cancelled);
      await loadJobHistory();
    } catch (err) {
      alert("Failed to cancel job.");
    } finally {
      setIsCancelling(false);
    }
  };

  const handleTriggerDiagnosis = async () => {
    if (!activeJob) return;
    setIsDiagnosing(true);
    try {
      const report = await triggerDiagnosis(activeJob.id);
      setDiagnostics((prev) => [report, ...prev]);
      setActiveDiagnostic(report);
      setIsDiagModalOpen(true);
    } catch (err: any) {
      alert(`Diagnosis Error: ${err.message || "Failed to run AI diagnosis."}`);
    } finally {
      setIsDiagnosing(false);
    }
  };

  const handleDiagnosticUpdated = (updated: DiagnosticReport) => {
    setActiveDiagnostic(updated);
    setDiagnostics((prev) =>
      prev.map((d) => (d.id === updated.id ? updated : d))
    );
  };

  const handleStartValidation = async (diagnosticId: string) => {
    setIsValidating(true);
    try {
      const valRun = await startPatchValidation(diagnosticId);
      setValidations((prev) => [valRun, ...prev]);
      setActiveValidation(valRun);

      try {
        const rep = await fetchFinalEvidenceReport(valRun.id);
        setFinalReport(rep);
      } catch {
        setFinalReport(null);
      }

      setIsFinalReportOpen(true);
    } catch (err: any) {
      alert(`Validation Error: ${err.message || "Failed to run patch validation."}`);
    } finally {
      setIsValidating(false);
    }
  };

  const handleOpenFinalReport = async (valRun: ValidationRun) => {
    setActiveValidation(valRun);
    try {
      const rep = await fetchFinalEvidenceReport(valRun.id);
      setFinalReport(rep);
    } catch {
      setFinalReport(null);
    }
    setIsFinalReportOpen(true);
  };

  const handleCopyLogs = () => {
    if (!logs) return;
    const content =
      activeTab === "stdout" ? logs.stdout : activeTab === "stderr" ? logs.stderr : logs.setup_logs;
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isRunning = activeJob && ["pending", "preparing", "running"].includes(activeJob.status);

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
      {/* Top Header & Trigger Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center space-x-2">
            <Terminal className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-bold text-white">Baseline Test Execution & Evidence Capture</h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Executes repository tests in an isolated, non-root Docker container with network disabled
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {isRunning ? (
            <button
              onClick={handleCancelRun}
              disabled={isCancelling}
              className="flex items-center space-x-2 px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-xl shadow-md transition"
            >
              <StopCircle className="w-4 h-4" />
              <span>{isCancelling ? "Cancelling..." : "Cancel Run"}</span>
            </button>
          ) : (
            <button
              onClick={handleStartRun}
              disabled={isStarting}
              className="flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-blue-600/30 transition active:scale-95 disabled:bg-blue-600/50"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>{isStarting ? "Dispatching Worker..." : "Run Baseline Tests"}</span>
            </button>
          )}

          {jobHistory.length > 1 && (
            <select
              value={activeJob?.id || ""}
              onChange={(e) => {
                const found = jobHistory.find((j) => j.id === e.target.value);
                if (found) selectJob(found);
              }}
              className="bg-slate-950 border border-slate-700 text-xs text-slate-300 rounded-lg px-2.5 py-2 focus:outline-none"
            >
              {jobHistory.map((j, i) => (
                <option key={j.id} value={j.id}>
                  Run #{jobHistory.length - i} — {j.status.toUpperCase()} ({new Date(j.created_at).toLocaleTimeString()})
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* No jobs executed yet empty state */}
      {!activeJob && (
        <div className="border border-dashed border-slate-800 rounded-xl p-8 text-center space-y-3">
          <Terminal className="w-10 h-10 text-slate-500 mx-auto" />
          <h3 className="text-sm font-semibold text-white">No Baseline Test Executions Yet</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Click &quot;Run Baseline Tests&quot; to auto-detect the test suite, create an isolated container environment,
            and capture real exit codes, test summaries, and failure tracebacks.
          </p>
        </div>
      )}

      {/* Active / Selected Job Content */}
      {activeJob && (
        <div className="space-y-6">
          {/* Status & Progress Banner */}
          <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center space-x-3">
                {activeJob.status === "completed" && (
                  <CheckCircle2 className="w-6 h-6 text-emerald-400 flex-shrink-0" />
                )}
                {activeJob.status === "failed" && (
                  <XCircle className="w-6 h-6 text-rose-400 flex-shrink-0" />
                )}
                {activeJob.status === "timed_out" && (
                  <Clock className="w-6 h-6 text-amber-400 flex-shrink-0" />
                )}
                {isRunning && (
                  <RefreshCw className="w-6 h-6 text-blue-400 animate-spin flex-shrink-0" />
                )}

                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-bold text-white uppercase tracking-wider">
                      {activeJob.status === "completed"
                        ? "Tests Passed"
                        : activeJob.status === "failed"
                        ? activeJob.error_type === "setup_error"
                          ? "Environment / Setup Limitation"
                          : activeJob.error_type === "syntax_error"
                          ? "Python Syntax Error"
                          : "Test Suite Failed"
                        : activeJob.status === "timed_out"
                        ? "Execution Timed Out"
                        : "Executing Tests"}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full font-mono bg-slate-800 text-slate-300">
                      Exit Code: {activeJob.exit_code ?? "—"}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    Stage: <span className="text-blue-300 font-medium">{STAGE_LABELS[activeJob.stage] || activeJob.stage}</span>
                  </div>
                </div>
              </div>

              {/* Execution Specs & Security Policy Badges */}
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>{activeJob.duration_seconds ? `${activeJob.duration_seconds}s` : "Running..."}</span>
                </span>
                <span className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
                  <Shield className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Network: Disabled (--network=none)</span>
                </span>
                <span className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
                  <Cpu className="w-3.5 h-3.5 text-blue-400" />
                  <span>{activeJob.image_version}</span>
                </span>
              </div>
            </div>

            {/* Error Message Alert (if setup or infrastructure error) */}
            {activeJob.error_message && activeJob.error_type !== "test_failure" && (
              <div className="bg-amber-950/40 border border-amber-800/80 rounded-lg p-3 text-xs text-amber-300 flex items-start space-x-2 mt-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold block mb-0.5">
                    {activeJob.error_type === "setup_error"
                      ? "Environment Setup Failure (Dependencies Unmet)"
                      : activeJob.error_type === "syntax_error"
                      ? "Syntax Error in Test Suite"
                      : "Execution Error"}
                  </span>
                  <span>{activeJob.error_message}</span>
                </div>
              </div>
            )}
          </div>

          {/* Test Counts Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl text-center">
              <span className="text-[11px] uppercase tracking-wider text-slate-400 block font-medium">Total Tests</span>
              <span className="text-xl font-bold text-white mt-1 block">{activeJob.tests_total}</span>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl text-center">
              <span className="text-[11px] uppercase tracking-wider text-emerald-400 block font-medium">Passed</span>
              <span className="text-xl font-bold text-emerald-400 mt-1 block">{activeJob.tests_passed}</span>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl text-center">
              <span className="text-[11px] uppercase tracking-wider text-rose-400 block font-medium">Failed</span>
              <span className="text-xl font-bold text-rose-400 mt-1 block">{activeJob.tests_failed}</span>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl text-center">
              <span className="text-[11px] uppercase tracking-wider text-amber-400 block font-medium">Errors</span>
              <span className="text-xl font-bold text-amber-400 mt-1 block">{activeJob.tests_errors}</span>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl text-center col-span-2 sm:col-span-1">
              <span className="text-[11px] uppercase tracking-wider text-slate-400 block font-medium">Skipped</span>
              <span className="text-xl font-bold text-slate-400 mt-1 block">{activeJob.tests_skipped}</span>
            </div>
          </div>

          {/* Captured Failures & Tracebacks */}
          {activeJob.failures && activeJob.failures.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center space-x-2 text-xs font-bold text-rose-300 uppercase tracking-wider">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <span>Captured Test Failures & Tracebacks ({activeJob.failures.length})</span>
              </div>

              <div className="space-y-3">
                {activeJob.failures.map((fail, idx) => {
                  const isExp = expandedTracebacks[idx] !== false;
                  return (
                    <div
                      key={idx}
                      className="bg-slate-950 border border-rose-900/60 rounded-xl overflow-hidden shadow-sm"
                    >
                      <div
                        onClick={() =>
                          setExpandedTracebacks((prev) => ({ ...prev, [idx]: !isExp }))
                        }
                        className="px-4 py-3 bg-rose-950/30 flex items-center justify-between cursor-pointer hover:bg-rose-950/50 transition text-xs"
                      >
                        <div className="flex items-center space-x-2 font-mono text-rose-200">
                          {isExp ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          <span className="font-semibold">{fail.test_name}</span>
                          {fail.file && (
                            <span className="text-slate-400 text-[11px]">
                              ({fail.file}{fail.line ? `:${fail.line}` : ""})
                            </span>
                          )}
                        </div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-900 text-rose-200">
                          FAILED
                        </span>
                      </div>

                      {isExp && (
                        <div className="p-4 bg-slate-950/90 border-t border-rose-900/40">
                          <pre className="font-mono text-xs text-rose-300 bg-black/40 p-3 rounded-lg overflow-x-auto whitespace-pre-wrap leading-relaxed select-all">
                            {fail.traceback}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* AI Root Cause Diagnosis & Safe Patch Proposals */}
          {(activeJob.tests_failed > 0 || activeJob.tests_errors > 0 || activeJob.status === "failed" || diagnostics.length > 0) && (
            <div className="bg-gradient-to-r from-purple-950/40 via-slate-900 to-slate-950 border border-purple-800/60 rounded-xl p-5 space-y-4 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center space-x-3">
                  <div className="p-2.5 rounded-xl bg-purple-500/20 text-purple-300 border border-purple-500/30">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="text-sm font-bold text-white">AI Diagnosis & Patch Proposal</h3>
                      {diagnostics.length > 0 && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-900 text-purple-200 uppercase">
                          {diagnostics.length} {diagnostics.length === 1 ? "Report" : "Reports"} Available
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Grounds diagnosis in actual traceback frames, AST imports, and repository context with multi-layer patch validation.
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  {diagnostics.length > 0 && (
                    <button
                      onClick={() => {
                        setActiveDiagnostic(diagnostics[0]);
                        setIsDiagModalOpen(true);
                      }}
                      className="px-4 py-2 bg-purple-950/80 hover:bg-purple-900 text-purple-200 border border-purple-700 rounded-xl text-xs font-semibold transition"
                    >
                      Review Latest Patch ({diagnostics[0].status.toUpperCase()})
                    </button>
                  )}

                  <button
                    onClick={handleTriggerDiagnosis}
                    disabled={isDiagnosing}
                    className="flex items-center space-x-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-purple-600/30 transition disabled:opacity-50"
                  >
                    <Sparkles className="w-4 h-4" />
                    <span>{isDiagnosing ? "Diagnosing with AI..." : diagnostics.length > 0 ? "Re-diagnose" : "Diagnose Failures with AI"}</span>
                  </button>
                </div>
              </div>

              {/* Latest Diagnostic Quick Summary Card */}
              {diagnostics.length > 0 && (
                <div className="bg-slate-950/80 border border-purple-900/40 rounded-lg p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div className="space-y-1">
                    <div className="text-purple-300 font-medium">
                      Hypothesis: <span className="text-white">{diagnostics[0].root_cause_hypothesis}</span>
                    </div>
                    <div className="text-slate-400 text-[11px] flex items-center space-x-3">
                      <span>Confidence: <strong className="text-purple-300">{Math.round(diagnostics[0].confidence_score * 100)}%</strong></span>
                      <span>•</span>
                      <span>Validation: <strong className={diagnostics[0].patch_validation_status === "valid" ? "text-emerald-400" : "text-rose-400"}>{diagnostics[0].patch_validation_status}</strong></span>
                      <span>•</span>
                      <span>Affected Files: {diagnostics[0].affected_files?.join(", ") || "None"}</span>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      setActiveDiagnostic(diagnostics[0]);
                      setIsDiagModalOpen(true);
                    }}
                    className="text-xs text-purple-400 hover:text-purple-300 underline font-semibold flex-shrink-0"
                  >
                    Open Full Inspection Drawer →
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Central Verdict & Validation Result Banner (Day 4) */}
          {validations.length > 0 && (
            <div
              className={`border rounded-xl p-5 space-y-4 shadow-sm ${
                validations[0].verdict === "VALIDATED"
                  ? "bg-gradient-to-r from-emerald-950/40 via-slate-900 to-slate-950 border-emerald-800/60"
                  : validations[0].verdict === "INFRASTRUCTURE_ERROR"
                  ? "bg-gradient-to-r from-rose-950/40 via-slate-900 to-slate-950 border-rose-800/60"
                  : "bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-950 border-amber-800/60"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center space-x-3">
                  <div
                    className={`p-2.5 rounded-xl border ${
                      validations[0].verdict === "VALIDATED"
                        ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                        : validations[0].verdict === "INFRASTRUCTURE_ERROR"
                        ? "bg-rose-500/20 text-rose-300 border-rose-500/30"
                        : "bg-amber-500/20 text-amber-300 border-amber-500/30"
                    }`}
                  >
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="text-sm font-bold text-white">Central Verdict: {validations[0].verdict}</h3>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 uppercase">
                        Attempt {validations[0].attempt_number} of {validations[0].max_attempts}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 mt-0.5">{validations[0].verdict_explanation}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => handleOpenFinalReport(validations[0])}
                    className="flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-600/30 transition"
                  >
                    <FileCode className="w-4 h-4" />
                    <span>View Evidence Report</span>
                  </button>
                </div>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Target Test</span>
                  <span className={validations[0].target_test_passed ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                    {validations[0].target_test_passed ? "RESOLVED (Passed)" : "STILL FAILING"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Regression Suite</span>
                  <span className={validations[0].regression_tests_passed ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                    {validations[0].regression_tests_passed ? "CLEAN (Passed)" : "REGRESSIONS"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Tests Passed</span>
                  <span className="text-white font-mono">{validations[0].patched_tests_passed} / {validations[0].patched_tests_total}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Workspace Hash</span>
                  <span className="text-slate-300 font-mono text-[11px]">{validations[0].workspace_hash?.slice(0, 10)}...</span>
                </div>
              </div>
            </div>
          )}

          {/* Bounded Execution Logs Viewer */}
          {logs && (
            <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
              <div className="px-4 py-2.5 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setActiveTab("stdout")}
                    className={`px-3 py-1 rounded text-xs font-medium transition ${
                      activeTab === "stdout"
                        ? "bg-blue-600 text-white"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Stdout
                  </button>
                  <button
                    onClick={() => setActiveTab("stderr")}
                    className={`px-3 py-1 rounded text-xs font-medium transition ${
                      activeTab === "stderr"
                        ? "bg-blue-600 text-white"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Stderr
                  </button>
                  {logs.setup_logs && (
                    <button
                      onClick={() => setActiveTab("setup")}
                      className={`px-3 py-1 rounded text-xs font-medium transition ${
                        activeTab === "setup"
                          ? "bg-blue-600 text-white"
                          : "text-slate-400 hover:text-white"
                      }`}
                    >
                      Preparation / Setup Logs
                    </button>
                  )}
                </div>

                <button
                  onClick={handleCopyLogs}
                  className="flex items-center space-x-1 text-xs text-slate-400 hover:text-white p-1 rounded transition"
                  title="Copy logs"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? "Copied" : "Copy"}</span>
                </button>
              </div>

              {/* Log Content */}
              <div className="p-4 bg-slate-950 font-mono text-xs text-slate-300 max-h-96 overflow-y-auto">
                <pre className="whitespace-pre-wrap leading-relaxed select-all">
                  {activeTab === "stdout"
                    ? logs.stdout || "(No stdout recorded)"
                    : activeTab === "stderr"
                    ? logs.stderr || "(No stderr recorded)"
                    : logs.setup_logs || "(No setup logs recorded)"}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {activeDiagnostic && (
        <DiagnosticReviewModal
          diagnostic={activeDiagnostic}
          isOpen={isDiagModalOpen}
          onClose={() => setIsDiagModalOpen(false)}
          onUpdated={handleDiagnosticUpdated}
          onRunValidation={handleStartValidation}
        />
      )}

      {activeValidation && (
        <FinalReportModal
          validationRun={activeValidation}
          report={finalReport}
          isOpen={isFinalReportOpen}
          onClose={() => setIsFinalReportOpen(false)}
        />
      )}
    </div>
  );
}
