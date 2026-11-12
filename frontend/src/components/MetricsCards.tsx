import React from "react";
import { Files, Code2, Beaker, FileText, AlertTriangle, FileX } from "lucide-react";
import { ScanJob } from "../lib/types";

interface MetricsCardsProps {
  scan?: ScanJob | null;
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export function MetricsCards({ scan }: MetricsCardsProps) {
  if (!scan) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {/* Total Files */}
      <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl shadow-sm hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Total Files</span>
          <Files className="w-4 h-4 text-blue-400" />
        </div>
        <div className="text-2xl font-bold text-white">{scan.total_files.toLocaleString()}</div>
        <div className="text-xs text-slate-500 mt-1">
          {scan.total_directories} dirs ({formatBytes(scan.total_size_bytes)})
        </div>
      </div>

      {/* Source Code */}
      <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl shadow-sm hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Source Files</span>
          <Code2 className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="text-2xl font-bold text-white">{scan.supported_source_files.toLocaleString()}</div>
        <div className="text-xs text-emerald-500 mt-1">Ready for analysis</div>
      </div>

      {/* Test Files */}
      <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl shadow-sm hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Tests</span>
          <Beaker className="w-4 h-4 text-purple-400" />
        </div>
        <div className="text-2xl font-bold text-white">{scan.test_files.toLocaleString()}</div>
        <div className="text-xs text-purple-400 mt-1 flex gap-1 flex-wrap">
          {scan.detected_frameworks.length > 0
            ? scan.detected_frameworks.join(", ")
            : "No framework"}
        </div>
      </div>

      {/* Manifests */}
      <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl shadow-sm hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Manifests</span>
          <FileText className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="text-2xl font-bold text-white">{scan.manifest_files.toLocaleString()}</div>
        <div className="text-xs text-slate-500 mt-1 truncate" title={scan.detected_manifests.join(", ")}>
          {scan.detected_manifests.length > 0 ? scan.detected_manifests.join(", ") : "None found"}
        </div>
      </div>

      {/* Skipped Files */}
      <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl shadow-sm hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Skipped</span>
          <FileX className="w-4 h-4 text-amber-400" />
        </div>
        <div className="text-2xl font-bold text-white">{scan.skipped_files.toLocaleString()}</div>
        <div className="text-xs text-amber-500 mt-1">Exclusions / limits</div>
      </div>

      {/* Parse Errors */}
      <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl shadow-sm hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Parse Errors</span>
          <AlertTriangle className={`w-4 h-4 ${scan.parse_errors > 0 ? "text-rose-400" : "text-slate-500"}`} />
        </div>
        <div className={`text-2xl font-bold ${scan.parse_errors > 0 ? "text-rose-400" : "text-white"}`}>
          {scan.parse_errors.toLocaleString()}
        </div>
        <div className="text-xs text-slate-500 mt-1">
          {scan.parse_errors > 0 ? "Syntax issues identified" : "Clean parse"}
        </div>
      </div>
    </div>
  );
}
