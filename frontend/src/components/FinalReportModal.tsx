"use client";

import React, { useState } from "react";
import {
  X,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Clock,
  Cpu,
  FileCode,
  Copy,
  Check,
  Download,
  Terminal,
  Layers,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { ValidationRun, FinalEvidenceReport } from "@/lib/types";

interface FinalReportModalProps {
  validationRun: ValidationRun;
  report?: FinalEvidenceReport | null;
  isOpen: boolean;
  onClose: () => void;
}

export function FinalReportModal({
  validationRun,
  report,
  isOpen,
  onClose,
}: FinalReportModalProps) {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"summary" | "comparison" | "diff" | "audit">("summary");

  if (!isOpen) return null;

  const handleCopyJson = () => {
    const dataToCopy = report || validationRun;
    navigator.clipboard.writeText(JSON.stringify(dataToCopy, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isSuccess = validationRun.verdict === "VALIDATED";
  const isInfra = validationRun.verdict === "INFRASTRUCTURE_ERROR";

  const renderDiffLines = (diff: string) => {
    if (!diff) {
      return (
        <div className="p-4 text-center text-slate-500 font-mono text-xs">
          No unified diff recorded for this patch version.
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
          } else if (line.startsWith("---") || line.startsWith("+++")) {
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-950 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center space-x-3">
            <div
              className={`p-2.5 rounded-xl border ${
                isSuccess
                  ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                  : isInfra
                  ? "bg-rose-500/10 border-rose-500/20 text-rose-400"
                  : "bg-amber-500/10 border-amber-500/20 text-amber-400"
              }`}
            >
              {isSuccess ? (
                <ShieldCheck className="w-6 h-6" />
              ) : isInfra ? (
                <ShieldAlert className="w-6 h-6" />
              ) : (
                <AlertTriangle className="w-6 h-6" />
              )}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-white">Evidence-Based Validation Report</h2>
                <span
                  className={`text-xs font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                    isSuccess
                      ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                      : isInfra
                      ? "bg-rose-950 text-rose-400 border border-rose-800"
                      : "bg-amber-950 text-amber-400 border border-amber-800"
                  }`}
                >
                  {validationRun.verdict}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Attempt {validationRun.attempt_number} of {validationRun.max_attempts} • Patch Version {validationRun.patch_version}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleCopyJson}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 transition"
              title="Copy Complete Report JSON"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? "Copied" : "JSON"}</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Verdict Explanation Banner */}
        <div
          className={`px-5 py-3.5 border-b text-xs flex items-start space-x-2.5 ${
            isSuccess
              ? "bg-emerald-950/40 border-emerald-900/60 text-emerald-200"
              : isInfra
              ? "bg-rose-950/40 border-rose-900/60 text-rose-200"
              : "bg-amber-950/40 border-amber-900/60 text-amber-200"
          }`}
        >
          <div className="mt-0.5 flex-shrink-0">
            {isSuccess ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : isInfra ? (
              <ShieldAlert className="w-4 h-4 text-rose-400" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-400" />
            )}
          </div>
          <div className="space-y-0.5">
            <span className="font-bold uppercase tracking-wider text-[11px] block">
              {validationRun.verdict_reason_code}
            </span>
            <p className="leading-relaxed">{validationRun.verdict_explanation}</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 px-5 space-x-4 text-xs font-semibold bg-slate-900/40">
          <button
            onClick={() => setActiveTab("summary")}
            className={`py-3 transition border-b-2 ${
              activeTab === "summary"
                ? "border-blue-400 text-blue-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Outcome Summary
          </button>
          <button
            onClick={() => setActiveTab("comparison")}
            className={`py-3 transition border-b-2 ${
              activeTab === "comparison"
                ? "border-blue-400 text-blue-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Before vs After Comparison
          </button>
          <button
            onClick={() => setActiveTab("diff")}
            className={`py-3 transition border-b-2 ${
              activeTab === "diff"
                ? "border-blue-400 text-blue-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Approved Patch Diff
          </button>
          <button
            onClick={() => setActiveTab("audit")}
            className={`py-3 transition border-b-2 ${
              activeTab === "audit"
                ? "border-blue-400 text-blue-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Audit & Environment Trail
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Tab 1: Summary */}
          {activeTab === "summary" && (
            <div className="space-y-4">
              {/* Primary Target Test Status Card */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                    Primary Failing Target Test
                  </span>
                  <div className="font-mono text-sm font-semibold text-white">
                    {validationRun.target_test_name || "(None identified)"}
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <span
                    className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                      validationRun.target_test_passed
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        : "bg-rose-950 text-rose-300 border border-rose-800"
                    }`}
                  >
                    {validationRun.target_test_passed ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Resolved in Patched Run</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Still Failing After Patch</span>
                      </>
                    )}
                  </span>
                </div>
              </div>

              {/* Regression Test Status Card */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                    Regression Suite Verification
                  </span>
                  <p className="text-xs text-slate-300">
                    {validationRun.regression_tests_passed
                      ? `All ${validationRun.patched_tests_passed} tests passed cleanly without introducing new failures.`
                      : `Regressions detected: ${validationRun.new_regressions?.join(", ") || `${validationRun.patched_tests_failed} test(s) failed.`}`}
                  </p>
                </div>

                <div className="flex items-center space-x-2">
                  <span
                    className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                      validationRun.regression_tests_passed
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        : "bg-rose-950 text-rose-300 border border-rose-800"
                    }`}
                  >
                    {validationRun.regression_tests_passed ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Clean Regression Run</span>
                      </>
                    ) : (
                      <>
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Regressions Introduced</span>
                      </>
                    )}
                  </span>
                </div>
              </div>

              {/* Segregated AI Hypothesis Card (explicitly labeled) */}
              {report?.ai_diagnosis_summary && (
                <div className="bg-purple-950/20 border border-purple-800/40 rounded-xl p-4 space-y-2">
                  <div className="flex items-center space-x-2 text-xs font-bold text-purple-300 uppercase tracking-wider">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Model-Generated Diagnosis (Unverified Hypothesis)</span>
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed">
                    {report.ai_diagnosis_summary.hypothesis}
                  </p>
                  <div className="text-[11px] text-slate-400 pt-1 flex items-center space-x-3">
                    <span>Model Confidence: <strong>{Math.round((report.ai_diagnosis_summary.confidence_score || 0) * 100)}%</strong></span>
                    <span>•</span>
                    <span>Provider: {report.ai_diagnosis_summary.llm_provider}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Comparison */}
          {activeTab === "comparison" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Baseline Metrics */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                      Baseline Run (Before Patch)
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">ID: {validationRun.baseline_job_id.slice(0, 8)}...</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="bg-slate-950 p-2 rounded-lg">
                      <span className="text-[10px] text-slate-400 block">Total</span>
                      <strong className="text-white text-base">{validationRun.baseline_tests_total}</strong>
                    </div>
                    <div className="bg-slate-950 p-2 rounded-lg">
                      <span className="text-[10px] text-emerald-400 block">Passed</span>
                      <strong className="text-emerald-400 text-base">{validationRun.baseline_tests_passed}</strong>
                    </div>
                    <div className="bg-slate-950 p-2 rounded-lg">
                      <span className="text-[10px] text-rose-400 block">Failed</span>
                      <strong className="text-rose-400 text-base">{validationRun.baseline_tests_failed}</strong>
                    </div>
                  </div>
                </div>

                {/* Patched Metrics */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-xs font-bold text-blue-300 uppercase tracking-wider">
                      Patched Run (After Patch)
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">ID: {validationRun.patched_job_id?.slice(0, 8) || "—"}</span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center text-xs">
                    <div className="bg-slate-950 p-2 rounded-lg">
                      <span className="text-[10px] text-slate-400 block">Total</span>
                      <strong className="text-white text-base">{validationRun.patched_tests_total}</strong>
                    </div>
                    <div className="bg-slate-950 p-2 rounded-lg">
                      <span className="text-[10px] text-emerald-400 block">Passed</span>
                      <strong className="text-emerald-400 text-base">{validationRun.patched_tests_passed}</strong>
                    </div>
                    <div className="bg-slate-950 p-2 rounded-lg">
                      <span className="text-[10px] text-rose-400 block">Failed</span>
                      <strong className="text-rose-400 text-base">{validationRun.patched_tests_failed}</strong>
                    </div>
                    <div className="bg-slate-950 p-2 rounded-lg">
                      <span className="text-[10px] text-amber-400 block">Errors</span>
                      <strong className="text-amber-400 text-base">{validationRun.patched_tests_errors}</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Resolved vs Regressed Lists */}
              <div className="space-y-2 text-xs">
                {validationRun.target_tests_resolved && validationRun.target_tests_resolved.length > 0 && (
                  <div className="bg-emerald-950/30 border border-emerald-900/50 rounded-xl p-3">
                    <span className="font-bold text-emerald-400 block mb-1">Resolved Failures ({validationRun.target_tests_resolved.length}):</span>
                    <ul className="list-disc list-inside font-mono text-[11px] text-emerald-300 space-y-0.5">
                      {validationRun.target_tests_resolved.map((t, idx) => (
                        <li key={idx}>{t}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {validationRun.new_regressions && validationRun.new_regressions.length > 0 && (
                  <div className="bg-rose-950/30 border border-rose-900/50 rounded-xl p-3">
                    <span className="font-bold text-rose-400 block mb-1">New Regressions Introduced ({validationRun.new_regressions.length}):</span>
                    <ul className="list-disc list-inside font-mono text-[11px] text-rose-300 space-y-0.5">
                      {validationRun.new_regressions.map((t, idx) => (
                        <li key={idx}>{t}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab 3: Diff */}
          {activeTab === "diff" && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between text-xs text-slate-400">
                <span className="font-medium">Applied Patch (Version {validationRun.patch_version}):</span>
                <span className="font-mono text-[11px]">Hash: {validationRun.patch_hash.slice(0, 16)}...</span>
              </div>
              <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden p-2 max-h-96 overflow-y-auto">
                {renderDiffLines(report?.patch_summary?.unified_diff || "")}
              </div>
            </div>
          )}

          {/* Tab 4: Audit */}
          {activeTab === "audit" && (
            <div className="space-y-3 text-xs">
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                <span className="font-bold text-slate-300 uppercase tracking-wider block">Cryptographic Hashes & IDs</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono text-[11px] text-slate-400">
                  <div>Validation Run ID: <span className="text-white">{validationRun.id}</span></div>
                  <div>Patch Hash (SHA-256): <span className="text-white">{validationRun.patch_hash.slice(0, 16)}...</span></div>
                  <div>Patched Workspace Hash: <span className="text-white">{validationRun.workspace_hash.slice(0, 16)}...</span></div>
                  <div>Attempt Number: <span className="text-white">{validationRun.attempt_number} of {validationRun.max_attempts}</span></div>
                </div>
              </div>

              {report?.limitations_and_caveats && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                  <span className="font-bold text-amber-400 uppercase tracking-wider block">Caveats & Formal Limitations</span>
                  <ul className="list-disc list-inside text-slate-300 space-y-1 text-[11px] leading-relaxed">
                    {report.limitations_and_caveats.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between text-xs">
          <div className="text-slate-400">
            Audit Trail Preserved • Original Upload Intact
          </div>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-semibold transition"
          >
            Close Report
          </button>
        </div>
      </div>
    </div>
  );
}
