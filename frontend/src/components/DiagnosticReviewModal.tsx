"use client";

import React, { useState } from "react";
import {
  X,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldAlert,
  FileCode,
  Sparkles,
  Check,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Clock,
  Cpu,
  Layers,
  ArrowRight,
  Play,
} from "lucide-react";
import { DiagnosticReport, EvidenceReference } from "@/lib/types";
import { approveDiagnostic, rejectDiagnostic } from "@/lib/api";

interface DiagnosticReviewModalProps {
  diagnostic: DiagnosticReport;
  isOpen: boolean;
  onClose: () => void;
  onUpdated: (updated: DiagnosticReport) => void;
  onRunValidation?: (diagnosticId: string) => void;
}

export function DiagnosticReviewModal({
  diagnostic,
  isOpen,
  onClose,
  onUpdated,
  onRunValidation,
}: DiagnosticReviewModalProps) {
  const [activeTab, setActiveTab] = useState<"diff" | "evidence" | "risks">("diff");
  const [reviewNotes, setReviewNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [expandedSnippets, setExpandedSnippets] = useState<Record<number, boolean>>({ 0: true });

  if (!isOpen) return null;

  const handleApprove = async () => {
    setIsSubmitting(true);
    setActionError(null);
    try {
      const updated = await approveDiagnostic(diagnostic.id, reviewNotes.trim() || undefined);
      onUpdated(updated);
    } catch (err: any) {
      setActionError(err.message || "Failed to approve patch.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    setIsSubmitting(true);
    setActionError(null);
    try {
      const updated = await rejectDiagnostic(diagnostic.id, reviewNotes.trim() || undefined);
      onUpdated(updated);
    } catch (err: any) {
      setActionError(err.message || "Failed to reject patch.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderDiffLines = (diff: string) => {
    if (!diff) {
      return (
        <div className="p-6 text-center text-slate-500 font-mono text-xs">
          No unified diff was proposed for this diagnostic report.
        </div>
      );
    }

    const lines = diff.split("\n");
    return (
      <div className="font-mono text-xs leading-relaxed overflow-x-auto select-all">
        {lines.map((line, idx) => {
          let lineClass = "text-slate-300 bg-transparent px-3 py-0.5";
          if (line.startsWith("+") && !line.startsWith("+++")) {
            lineClass = "text-emerald-300 bg-emerald-950/40 border-l-2 border-emerald-500 px-3 py-0.5";
          } else if (line.startsWith("-") && !line.startsWith("---")) {
            lineClass = "text-rose-300 bg-rose-950/40 border-l-2 border-rose-500 px-3 py-0.5";
          } else if (line.startsWith("@@")) {
            lineClass = "text-cyan-400 bg-slate-900/90 font-bold px-3 py-1 my-1";
          } else if (line.startsWith("diff ") || line.startsWith("index ") || line.startsWith("---") || line.startsWith("+++")) {
            lineClass = "text-slate-400 font-semibold px-3 py-0.5";
          }
          return (
            <div key={idx} className={lineClass}>
              {line || " "}
            </div>
          );
        })}
      </div>
    );
  };

  const isValidForApproval =
    diagnostic.patch_validation_status === "valid" &&
    diagnostic.unified_diff &&
    !diagnostic.is_insufficient_evidence;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-950 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-white">AI Diagnosis & Patch Proposal</h2>
                <span
                  className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                    diagnostic.status === "approved"
                      ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                      : diagnostic.status === "rejected"
                      ? "bg-rose-950 text-rose-400 border border-rose-800"
                      : "bg-amber-950 text-amber-400 border border-amber-800"
                  }`}
                >
                  {diagnostic.status}
                </span>
              </div>
              <div className="flex items-center space-x-3 text-xs text-slate-400 mt-0.5">
                <span className="flex items-center space-x-1">
                  <Cpu className="w-3.5 h-3.5 text-blue-400" />
                  <span>{diagnostic.llm_provider}</span>
                </span>
                <span>•</span>
                <span className="flex items-center space-x-1">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>{diagnostic.llm_duration_seconds.toFixed(2)}s inference</span>
                </span>
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Action Error Notification */}
        {actionError && (
          <div className="bg-rose-950/60 border-b border-rose-800 p-3 text-xs text-rose-300 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Modal Body (Scrollable) */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Hypothesis & Confidence Overview */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-purple-400">
                  Root Cause Hypothesis
                </span>
                <p className="text-sm font-semibold text-white mt-1 leading-relaxed">
                  {diagnostic.root_cause_hypothesis}
                </p>
              </div>

              {/* Confidence Score Pill */}
              <div className="flex-shrink-0 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-right">
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Confidence</div>
                <div className="text-lg font-black text-purple-300">
                  {Math.round(diagnostic.confidence_score * 100)}%
                </div>
              </div>
            </div>

            <p className="text-xs text-slate-400 border-t border-slate-800/80 pt-2.5">
              {diagnostic.confidence_explanation}
            </p>

            {/* Insufficient Evidence Warning */}
            {diagnostic.is_insufficient_evidence && (
              <div className="bg-amber-950/40 border border-amber-800/80 rounded-lg p-3 text-xs text-amber-300 flex items-start space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold block mb-0.5">Insufficient Diagnostic Evidence</span>
                  <span>
                    {diagnostic.insufficient_evidence_reason ||
                      "The model determined that repository context was inadequate to propose a safe patch."}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Validation Engine Status Banner */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/40 border border-slate-800 rounded-xl px-4 py-3 text-xs">
            <div className="flex items-center space-x-2">
              <span className="text-slate-400">Patch Security & Syntax Validation:</span>
              {diagnostic.patch_validation_status === "valid" ? (
                <span className="inline-flex items-center space-x-1 font-semibold text-emerald-400 bg-emerald-950/70 border border-emerald-800 px-2.5 py-0.5 rounded-full">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Valid & Syntax-Verified</span>
                </span>
              ) : diagnostic.patch_validation_status === "rejected_security" ? (
                <span className="inline-flex items-center space-x-1 font-semibold text-rose-400 bg-rose-950/70 border border-rose-800 px-2.5 py-0.5 rounded-full">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>Security Rejection (Traversal / Forbidden Target)</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 font-semibold text-amber-400 bg-amber-950/70 border border-amber-800 px-2.5 py-0.5 rounded-full">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>{diagnostic.patch_validation_status}</span>
                </span>
              )}
            </div>

            {diagnostic.patch_hash && (
              <div className="text-[11px] font-mono text-slate-400">
                Patch SHA: <span className="text-slate-200">{diagnostic.patch_hash.slice(0, 12)}...</span>
              </div>
            )}
          </div>

          {/* Validation Errors List if any */}
          {diagnostic.patch_validation_errors && diagnostic.patch_validation_errors.length > 0 && (
            <div className="bg-rose-950/30 border border-rose-800/80 rounded-xl p-3 text-xs space-y-1">
              <div className="font-semibold text-rose-300 flex items-center space-x-1.5">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                <span>Patch Validation Errors:</span>
              </div>
              <ul className="list-disc list-inside text-rose-200/90 pl-1 space-y-0.5 font-mono text-[11px]">
                {diagnostic.patch_validation_errors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Navigation Tabs */}
          <div className="flex border-b border-slate-800 space-x-4 text-xs font-semibold">
            <button
              onClick={() => setActiveTab("diff")}
              className={`pb-2.5 transition border-b-2 ${
                activeTab === "diff"
                  ? "border-purple-400 text-purple-300"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Proposed Patch (Unified Diff)
            </button>
            <button
              onClick={() => setActiveTab("evidence")}
              className={`pb-2.5 transition border-b-2 ${
                activeTab === "evidence"
                  ? "border-purple-400 text-purple-300"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Inspected Evidence & AST ({diagnostic.supporting_evidence.length})
            </button>
            <button
              onClick={() => setActiveTab("risks")}
              className={`pb-2.5 transition border-b-2 ${
                activeTab === "risks"
                  ? "border-purple-400 text-purple-300"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Risk Assessment & Tests
            </button>
          </div>

          {/* Tab 1: Proposed Diff */}
          {activeTab === "diff" && (
            <div className="space-y-3">
              {diagnostic.affected_files && diagnostic.affected_files.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <span className="font-medium">Affected Files:</span>
                  {diagnostic.affected_files.map((f) => (
                    <span
                      key={f}
                      className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 font-mono text-[11px] text-blue-300"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              )}

              <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                <div className="p-3 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between text-xs text-slate-400">
                  <span className="font-mono">unified-diff</span>
                  <span className="text-[11px]">Dry-run verified against AST</span>
                </div>
                <div className="p-2 max-h-96 overflow-y-auto">
                  {renderDiffLines(diagnostic.unified_diff)}
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Supporting Evidence */}
          {activeTab === "evidence" && (
            <div className="space-y-3">
              {diagnostic.files_inspected && diagnostic.files_inspected.length > 0 && (
                <div className="text-xs text-slate-400">
                  <span className="font-medium text-slate-300">Files Inspected for Diagnosis: </span>
                  <span className="font-mono text-[11px]">
                    {diagnostic.files_inspected.join(", ")}
                  </span>
                </div>
              )}

              {diagnostic.supporting_evidence.length === 0 ? (
                <p className="text-xs text-slate-500 py-4 text-center">No explicit code snippets recorded.</p>
              ) : (
                diagnostic.supporting_evidence.map((ev, idx) => {
                  const isExp = expandedSnippets[idx] !== false;
                  return (
                    <div
                      key={idx}
                      className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden"
                    >
                      <div
                        onClick={() =>
                          setExpandedSnippets((prev) => ({ ...prev, [idx]: !isExp }))
                        }
                        className="px-4 py-2.5 bg-slate-900/60 flex items-center justify-between cursor-pointer hover:bg-slate-900 text-xs"
                      >
                        <div className="flex items-center space-x-2 font-mono text-purple-300">
                          {isExp ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                          <FileCode className="w-3.5 h-3.5 text-blue-400" />
                          <span className="font-semibold">{ev.file_path}</span>
                          <span className="text-slate-500 text-[11px]">
                            (Lines {ev.line_start}–{ev.line_end})
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-400">{ev.description}</span>
                      </div>

                      {isExp && (
                        <div className="p-3 bg-black/40 border-t border-slate-900 font-mono text-xs text-slate-300 overflow-x-auto select-all">
                          <pre>{ev.snippet}</pre>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Tab 3: Risk Assessment */}
          {activeTab === "risks" && (
            <div className="space-y-4 text-xs">
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                <span className="font-semibold uppercase tracking-wider text-amber-400 block">
                  Potential Regression Risks
                </span>
                <p className="text-slate-300 leading-relaxed">
                  {diagnostic.potential_regression_risks || "None identified by the diagnostic model."}
                </p>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                <span className="font-semibold uppercase tracking-wider text-emerald-400 block">
                  Recommended Verification Tests
                </span>
                <p className="text-slate-300 leading-relaxed font-mono text-[11px]">
                  {diagnostic.recommended_tests || "Run baseline test suite to verify fix."}
                </p>
              </div>

              {diagnostic.known_limitations && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                  <span className="font-semibold uppercase tracking-wider text-slate-400 block">
                    Known Limitations
                  </span>
                  <p className="text-slate-400 leading-relaxed">
                    {diagnostic.known_limitations}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer / Human Review Controls */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 space-y-3">
          {diagnostic.status === "proposed" ? (
            <div className="space-y-3">
              <div className="flex items-center space-x-3">
                <input
                  type="text"
                  placeholder="Optional review notes or rejection reason..."
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="text-[11px] text-slate-400">
                  {!isValidForApproval && (
                    <span className="text-amber-400">
                      Approval disabled: patch validation status is &apos;{diagnostic.patch_validation_status}&apos;
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-3">
                  <button
                    onClick={handleReject}
                    disabled={isSubmitting}
                    className="flex items-center space-x-1.5 px-4 py-2 bg-rose-950/80 hover:bg-rose-900 text-rose-200 border border-rose-800 rounded-xl text-xs font-semibold transition"
                  >
                    <XCircle className="w-4 h-4" />
                    <span>{isSubmitting ? "Processing..." : "Reject Patch"}</span>
                  </button>

                  <button
                    onClick={handleApprove}
                    disabled={isSubmitting || !isValidForApproval}
                    className="flex items-center space-x-1.5 px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-emerald-600/30 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>{isSubmitting ? "Approving..." : "Approve Patch"}</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2">
                <span className="text-slate-400">Review Outcome:</span>
                <span
                  className={`font-bold uppercase ${
                    diagnostic.status === "approved" ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {diagnostic.status}
                </span>
                {diagnostic.review_notes && (
                  <span className="text-slate-400 italic">(&quot;{diagnostic.review_notes}&quot;)</span>
                )}
              </div>
              <div className="flex items-center space-x-2">
                {diagnostic.status === "approved" && onRunValidation && (
                  <button
                    onClick={() => {
                      onClose();
                      onRunValidation(diagnostic.id);
                    }}
                    className="flex items-center space-x-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-blue-600/30 transition"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Run Validation in Sandbox</span>
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
