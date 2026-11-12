import React from "react";

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";

  switch (status.toLowerCase()) {
    case "completed":
    case "content_analyzed":
      return (
        <span className={`inline-flex items-center font-medium rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800 ${sizeClasses}`}>
          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-400"></span>
          Analyzed
        </span>
      );
    case "running":
    case "analyzing":
      return (
        <span className={`inline-flex items-center font-medium rounded-full bg-blue-950/80 text-blue-400 border border-blue-800 animate-pulse ${sizeClasses}`}>
          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-blue-400"></span>
          Analyzing
        </span>
      );
    case "inventoried":
      return (
        <span className={`inline-flex items-center font-medium rounded-full bg-slate-800 text-slate-300 border border-slate-700 ${sizeClasses}`}>
          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-slate-400"></span>
          Inventoried
        </span>
      );
    case "skipped":
      return (
        <span className={`inline-flex items-center font-medium rounded-full bg-amber-950/80 text-amber-400 border border-amber-800 ${sizeClasses}`}>
          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-amber-400"></span>
          Skipped
        </span>
      );
    case "failed":
      return (
        <span className={`inline-flex items-center font-medium rounded-full bg-rose-950/80 text-rose-400 border border-rose-800 ${sizeClasses}`}>
          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-rose-400"></span>
          Failed
        </span>
      );
    default:
      return (
        <span className={`inline-flex items-center font-medium rounded-full bg-slate-800 text-slate-400 border border-slate-700 ${sizeClasses}`}>
          {status}
        </span>
      );
  }
}

interface ClassificationBadgeProps {
  classification: string;
}

export function ClassificationBadge({ classification }: ClassificationBadgeProps) {
  switch (classification.toLowerCase()) {
    case "test":
      return (
        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-purple-950/80 text-purple-300 border border-purple-800">
          TEST
        </span>
      );
    case "source_code":
      return (
        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-blue-950/80 text-blue-300 border border-blue-800">
          SOURCE
        </span>
      );
    case "configuration":
      return (
        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800">
          CONFIG
        </span>
      );
    case "documentation":
      return (
        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
          DOCS
        </span>
      );
    case "binary_data":
      return (
        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-orange-950/80 text-orange-300 border border-orange-800">
          BINARY
        </span>
      );
    case "generated_output":
      return (
        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-stone-900 text-stone-400 border border-stone-800">
          GENERATED
        </span>
      );
    default:
      return (
        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-800 text-slate-400 border border-slate-700">
          {classification.toUpperCase()}
        </span>
      );
  }
}
