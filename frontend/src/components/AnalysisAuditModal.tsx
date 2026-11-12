"use client";

import React, { useState } from "react";
import {
  X,
  ShieldCheck,
  ShieldAlert,
  FileCode,
  FolderTree,
  AlertTriangle,
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  FileText,
  Settings,
  Layers,
  Cpu,
} from "lucide-react";
import { AnalysisAuditSummary } from "@/lib/types";

interface AnalysisAuditModalProps {
  audit: AnalysisAuditSummary | null;
  isOpen: boolean;
  onClose: () => void;
}

export function AnalysisAuditModal({ audit, isOpen, onClose }: AnalysisAuditModalProps) {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "ast" | "skipped" | "categories">("overview");

  if (!isOpen || !audit) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(audit, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isFullCoverage = audit.content_analysis_coverage_pct === 100.0;
  const hasSkips = audit.files_skipped_limits_or_unsupported_count > 0 || audit.files_excluded_by_policy_count > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-950 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-white">Repository Analysis Audit & Coverage</h2>
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">
                  {audit.repository_name}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Audit metrics, AST parsing health, policy exclusions, and verified content coverage
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleCopy}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 transition"
              title="Copy Complete Audit JSON"
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

        {/* Coverage Percentage Banner */}
        <div className="px-5 py-4 bg-gradient-to-r from-blue-950/40 via-slate-900 to-slate-950 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-blue-300">
              Verified Content Analysis Coverage
            </div>
            <div className="text-xs text-slate-300">
              {hasSkips ? (
                <span>
                  {audit.files_content_analyzed} of {audit.total_discovered_files} discovered files deeply analyzed.
                  <span className="text-amber-300 ml-1">
                    Coverage is strictly capped at {audit.content_analysis_coverage_pct}% because {audit.files_skipped_limits_or_unsupported_count} file(s) or exclusions were skipped by policy or unsupported formats.
                  </span>
                </span>
              ) : (
                <span>100% of discovered files were content-analyzed without skips or unsupported formats.</span>
              )}
            </div>
          </div>

          <div className="flex-shrink-0 bg-slate-950 border border-blue-900/60 rounded-xl px-5 py-2.5 text-center">
            <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">Coverage</span>
            <span className="text-2xl font-black text-blue-400 font-mono">
              {audit.content_analysis_coverage_pct}%
            </span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 px-5 space-x-4 text-xs font-semibold bg-slate-900/40">
          <button
            onClick={() => setActiveTab("overview")}
            className={`py-3 transition border-b-2 ${
              activeTab === "overview"
                ? "border-blue-400 text-blue-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Audit Overview
          </button>
          <button
            onClick={() => setActiveTab("ast")}
            className={`py-3 transition border-b-2 ${
              activeTab === "ast"
                ? "border-blue-400 text-blue-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Python AST Parsing ({audit.ast_parse_successes} Pass / {audit.ast_parse_failures} Fail)
          </button>
          <button
            onClick={() => setActiveTab("skipped")}
            className={`py-3 transition border-b-2 ${
              activeTab === "skipped"
                ? "border-blue-400 text-blue-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Skipped & Excluded ({audit.files_skipped_limits_or_unsupported_count + audit.files_excluded_by_policy_count})
          </button>
          <button
            onClick={() => setActiveTab("categories")}
            className={`py-3 transition border-b-2 ${
              activeTab === "categories"
                ? "border-blue-400 text-blue-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Discovered Classification
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Tab 1: Overview */}
          {activeTab === "overview" && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] uppercase text-slate-400 block font-medium">Discovered Files</span>
                  <span className="text-xl font-bold text-white mt-1 block font-mono">{audit.total_discovered_files}</span>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] uppercase text-slate-400 block font-medium">Directories</span>
                  <span className="text-xl font-bold text-white mt-1 block font-mono">{audit.total_discovered_directories}</span>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] uppercase text-emerald-400 block font-medium">Content Analyzed</span>
                  <span className="text-xl font-bold text-emerald-400 mt-1 block font-mono">{audit.files_content_analyzed}</span>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] uppercase text-amber-400 block font-medium">Skipped / Excluded</span>
                  <span className="text-xl font-bold text-amber-400 mt-1 block font-mono">
                    {audit.files_skipped_limits_or_unsupported_count + audit.files_excluded_by_policy_count}
                  </span>
                </div>
              </div>

              {/* Detected Intelligence Badges */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3 text-xs">
                <span className="font-semibold text-slate-200 block uppercase tracking-wider text-[11px]">
                  Detected Test Frameworks & Manifests
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  {audit.detected_frameworks.length > 0 ? (
                    audit.detected_frameworks.map((fw) => (
                      <span
                        key={fw}
                        className="px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-950 text-purple-300 border border-purple-800 font-mono"
                      >
                        Framework: {fw}
                      </span>
                    ))
                  ) : (
                    <span className="text-slate-500">No test framework configs detected.</span>
                  )}
                  {audit.detected_manifests.map((mf) => (
                    <span
                      key={mf}
                      className="px-2.5 py-1 rounded-full text-xs font-semibold bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono"
                    >
                      Manifest: {mf}
                    </span>
                  ))}
                </div>
              </div>

              {/* Explicit Errors Alert */}
              {audit.explicit_analysis_errors_count > 0 && (
                <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-4 space-y-2 text-xs">
                  <div className="flex items-center space-x-2 font-semibold text-rose-300 uppercase tracking-wider text-[11px]">
                    <AlertTriangle className="w-4 h-4 text-rose-400" />
                    <span>Explicit Analysis Errors ({audit.explicit_analysis_errors_count}):</span>
                  </div>
                  <ul className="list-disc list-inside text-rose-200 space-y-1 font-mono text-[11px]">
                    {audit.explicit_errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Tab 2: AST Parsing */}
          {activeTab === "ast" && (
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] uppercase text-slate-400 block font-medium">Python Files</span>
                  <span className="text-xl font-bold text-white mt-1 block font-mono">{audit.python_files_total}</span>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] uppercase text-emerald-400 block font-medium">AST Parse Clean</span>
                  <span className="text-xl font-bold text-emerald-400 mt-1 block font-mono">{audit.ast_parse_successes}</span>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] uppercase text-rose-400 block font-medium">Syntax Errors</span>
                  <span className="text-xl font-bold text-rose-400 mt-1 block font-mono">{audit.ast_parse_failures}</span>
                </div>
              </div>

              {audit.ast_syntax_errors.length === 0 ? (
                <div className="p-6 text-center text-slate-400 bg-slate-900/40 border border-slate-800 rounded-xl">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                  <span>All Python source files parsed cleanly with zero syntax errors.</span>
                </div>
              ) : (
                <div className="space-y-2">
                  <span className="font-semibold text-rose-300 block uppercase tracking-wider text-[11px]">
                    Captured Syntax Errors:
                  </span>
                  {audit.ast_syntax_errors.map((err, idx) => (
                    <div
                      key={idx}
                      className="bg-slate-950 border border-rose-900/60 rounded-xl p-3.5 space-y-1 font-mono"
                    >
                      <div className="flex items-center justify-between text-rose-300">
                        <span className="font-bold">{err.relative_path}</span>
                        {err.lineno && <span className="text-slate-400">Line {err.lineno}</span>}
                      </div>
                      <p className="text-slate-300 text-[11px] font-sans">{err.error_message}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Skipped & Excluded */}
          {activeTab === "skipped" && (
            <div className="space-y-4 text-xs">
              {audit.excluded_directories.length > 0 && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                  <span className="font-semibold text-amber-300 block uppercase tracking-wider text-[11px]">
                    Directories Excluded by Policy ({audit.excluded_directories.length}):
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {audit.excluded_directories.map((dir) => (
                      <span
                        key={dir}
                        className="px-2 py-0.5 rounded bg-slate-950 border border-slate-700 font-mono text-[11px] text-amber-200"
                      >
                        {dir}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {audit.skipped_files.length === 0 ? (
                <p className="p-4 text-center text-slate-500">No individual files were skipped.</p>
              ) : (
                <div className="space-y-2">
                  <span className="font-semibold text-slate-300 block uppercase tracking-wider text-[11px]">
                    Files Skipped from Content Analysis ({audit.skipped_files.length}):
                  </span>
                  <div className="border border-slate-800 rounded-xl overflow-hidden">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 text-[10px] uppercase">
                        <tr>
                          <th className="px-3 py-2">Path</th>
                          <th className="px-3 py-2">Category</th>
                          <th className="px-3 py-2">Skip Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 text-slate-300">
                        {audit.skipped_files.map((sf, idx) => (
                          <tr key={idx} className="hover:bg-slate-900/50">
                            <td className="px-3 py-2 text-white">{sf.relative_path}</td>
                            <td className="px-3 py-2 font-sans capitalize">{sf.classification}</td>
                            <td className="px-3 py-2 font-sans text-slate-400 text-[11px]">{sf.skip_reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab 4: Categories */}
          {activeTab === "categories" && (
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] text-slate-400 block uppercase">Source Code</span>
                  <strong className="text-white text-lg font-mono">{audit.category_counts.source_code}</strong>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] text-purple-400 block uppercase">Test Files</span>
                  <strong className="text-purple-300 text-lg font-mono">{audit.test_files_count}</strong>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] text-cyan-400 block uppercase">Configuration</span>
                  <strong className="text-cyan-300 text-lg font-mono">{audit.configuration_files_count}</strong>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] text-slate-400 block uppercase">Documentation</span>
                  <strong className="text-slate-200 text-lg font-mono">{audit.category_counts.documentation}</strong>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] text-slate-400 block uppercase">Binary Data</span>
                  <strong className="text-slate-400 text-lg font-mono">{audit.category_counts.binary_data}</strong>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] text-slate-400 block uppercase">Generated Output</span>
                  <strong className="text-slate-400 text-lg font-mono">{audit.category_counts.generated_output}</strong>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] text-slate-400 block uppercase">Manifest Files</span>
                  <strong className="text-cyan-400 text-lg font-mono">{audit.manifest_files_count}</strong>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] text-slate-400 block uppercase">Other / Untyped</span>
                  <strong className="text-slate-400 text-lg font-mono">{audit.category_counts.other}</strong>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between text-xs">
          <div className="text-slate-400">
            Repository Analysis Audit • Never Reports 100% If Files Skipped
          </div>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-semibold transition"
          >
            Close Audit
          </button>
        </div>
      </div>
    </div>
  );
}
