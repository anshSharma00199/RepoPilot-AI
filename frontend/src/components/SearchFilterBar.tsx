"use client";

import React from "react";
import { Search, Filter, AlertTriangle, FolderTree, List } from "lucide-react";

interface SearchFilterBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  classification: string;
  onClassificationChange: (value: string) => void;
  status: string;
  onStatusChange: (value: string) => void;
  parseErrorsOnly: boolean;
  onParseErrorsOnlyChange: (value: boolean) => void;
  viewMode: "tree" | "list";
  onViewModeChange: (mode: "tree" | "list") => void;
}

export function SearchFilterBar({
  search,
  onSearchChange,
  classification,
  onClassificationChange,
  status,
  onStatusChange,
  parseErrorsOnly,
  onParseErrorsOnlyChange,
  viewMode,
  onViewModeChange,
}: SearchFilterBarProps) {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 flex flex-col md:flex-row items-center justify-between gap-3 shadow-sm">
      {/* Left side: Search input */}
      <div className="relative w-full md:w-80">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search files or paths..."
          className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-700/80 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
        />
      </div>

      {/* Center: Dropdown filters */}
      <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
        {/* Classification */}
        <select
          value={classification}
          onChange={(e) => onClassificationChange(e.target.value)}
          className="bg-slate-950 border border-slate-700/80 text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
        >
          <option value="">All Classifications</option>
          <option value="source_code">Source Code</option>
          <option value="test">Tests</option>
          <option value="configuration">Configuration</option>
          <option value="documentation">Documentation</option>
          <option value="binary_data">Binary</option>
        </select>

        {/* Status */}
        <select
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
          className="bg-slate-950 border border-slate-700/80 text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
        >
          <option value="">All Statuses</option>
          <option value="content_analyzed">Analyzed</option>
          <option value="inventoried">Inventoried</option>
          <option value="skipped">Skipped</option>
          <option value="failed">Failed</option>
        </select>

        {/* Parse errors toggle */}
        <button
          onClick={() => onParseErrorsOnlyChange(!parseErrorsOnly)}
          className={`flex items-center space-x-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition ${
            parseErrorsOnly
              ? "bg-rose-950/80 text-rose-300 border-rose-800 font-medium"
              : "bg-slate-950 text-slate-400 border-slate-700/80 hover:text-slate-200"
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>Parse Errors</span>
        </button>
      </div>

      {/* Right side: View mode toggle */}
      <div className="flex items-center border border-slate-700/80 rounded-lg p-0.5 bg-slate-950 ml-auto">
        <button
          onClick={() => onViewModeChange("tree")}
          title="Tree View"
          className={`px-2.5 py-1 rounded text-xs flex items-center space-x-1 transition ${
            viewMode === "tree"
              ? "bg-blue-600 text-white shadow-sm font-medium"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <FolderTree className="w-3.5 h-3.5" />
          <span>Tree</span>
        </button>
        <button
          onClick={() => onViewModeChange("list")}
          title="List / Table View"
          className={`px-2.5 py-1 rounded text-xs flex items-center space-x-1 transition ${
            viewMode === "list"
              ? "bg-blue-600 text-white shadow-sm font-medium"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <List className="w-3.5 h-3.5" />
          <span>List</span>
        </button>
      </div>
    </div>
  );
}
