"use client";

import React from "react";
import {
  X,
  FileCode,
  AlertTriangle,
  Boxes,
  FunctionSquare,
  PackageCheck,
  Hash,
  Info,
  CheckCircle,
} from "lucide-react";
import { RepositoryFile } from "../lib/types";
import { StatusBadge, ClassificationBadge } from "./StatusBadge";
import { formatBytes } from "./MetricsCards";

interface FileDetailDrawerProps {
  file: RepositoryFile | null;
  onClose: () => void;
}

export function FileDetailDrawer({ file, onClose }: FileDetailDrawerProps) {
  if (!file) return null;

  const ast = file.ast_metadata;
  const syntaxError = ast?.syntax_error;
  const classes = ast?.classes || [];
  const functions = ast?.functions || [];
  const imports = ast?.imports || [];
  const manifestInfo = ast?.manifest_info;

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-md bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
        <div className="flex items-center space-x-2 truncate">
          <FileCode className="w-5 h-5 text-blue-400 flex-shrink-0" />
          <h3 className="text-sm font-semibold text-white truncate" title={file.relative_path}>
            {file.relative_path.split("/").pop()}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Full Path */}
        <div>
          <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Relative Path
          </label>
          <div className="mt-1 font-mono text-xs text-slate-200 bg-slate-950 border border-slate-800 rounded-lg p-2.5 break-all select-all">
            {file.relative_path}
          </div>
        </div>

        {/* Badges & Meta */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-slate-950/50 border border-slate-800/80 rounded-lg p-3">
            <span className="text-xs text-slate-400 block mb-1">Classification</span>
            <ClassificationBadge classification={file.classification} />
          </div>
          <div className="bg-slate-950/50 border border-slate-800/80 rounded-lg p-3">
            <span className="text-xs text-slate-400 block mb-1">Analysis Status</span>
            <StatusBadge status={file.status} />
          </div>
        </div>

        {/* File Attributes */}
        <div className="bg-slate-950/50 border border-slate-800/80 rounded-lg p-3 space-y-2 text-xs">
          <div className="flex justify-between py-1 border-b border-slate-800/60">
            <span className="text-slate-400">Detected Language</span>
            <span className="font-medium text-slate-200 capitalize">{file.language}</span>
          </div>
          <div className="flex justify-between py-1 border-b border-slate-800/60">
            <span className="text-slate-400">File Size</span>
            <span className="font-mono text-slate-200">{formatBytes(file.file_size_bytes)}</span>
          </div>
          <div className="flex justify-between py-1 border-b border-slate-800/60">
            <span className="text-slate-400">Test File Flag</span>
            <span className={`font-semibold ${file.is_test ? "text-purple-400" : "text-slate-500"}`}>
              {file.is_test ? "Yes (Detected)" : "No"}
            </span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-slate-400">Manifest Flag</span>
            <span className={`font-semibold ${file.is_manifest ? "text-cyan-400" : "text-slate-500"}`}>
              {file.is_manifest ? "Yes (Manifest)" : "No"}
            </span>
          </div>
        </div>

        {/* Skip Reason (if applicable) */}
        {file.skip_reason && (
          <div className="bg-amber-950/40 border border-amber-800/60 rounded-xl p-3 text-xs text-amber-300 flex items-start space-x-2">
            <Info className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <span className="font-semibold block mb-0.5">Skip Reason:</span>
              <span>{file.skip_reason}</span>
            </div>
          </div>
        )}

        {/* SHA-256 Hash */}
        {file.file_hash && (
          <div>
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center space-x-1">
              <Hash className="w-3.5 h-3.5" />
              <span>SHA-256 Hash</span>
            </label>
            <div className="mt-1 font-mono text-[11px] text-slate-400 bg-slate-950 border border-slate-800 rounded p-2 break-all select-all">
              {file.file_hash}
            </div>
          </div>
        )}

        {/* Syntax Error Box */}
        {syntaxError && (
          <div className="bg-rose-950/60 border border-rose-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center space-x-2 text-rose-300 font-semibold text-xs">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              <span>Python AST Syntax Error</span>
            </div>
            <div className="text-xs text-rose-200">
              <span className="font-semibold">{syntaxError.message}</span>
              {syntaxError.lineno && <span> (line {syntaxError.lineno}, offset {syntaxError.offset})</span>}
            </div>
            {syntaxError.text && (
              <pre className="text-[11px] font-mono bg-rose-950 border border-rose-900 rounded p-2 text-rose-300 overflow-x-auto">
                {syntaxError.text}
              </pre>
            )}
          </div>
        )}

        {/* AST Classes */}
        {classes.length > 0 && (
          <div>
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center space-x-1.5 mb-2">
              <Boxes className="w-3.5 h-3.5 text-blue-400" />
              <span>Declared Classes ({classes.length})</span>
            </label>
            <div className="space-y-1.5">
              {classes.map((cls, idx) => (
                <div
                  key={idx}
                  className="bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs flex items-center justify-between"
                >
                  <div>
                    <span className="font-mono font-medium text-blue-300">{cls.name}</span>
                    {cls.bases.length > 0 && (
                      <span className="text-slate-500 text-[11px] ml-1">({cls.bases.join(", ")})</span>
                    )}
                  </div>
                  {cls.is_test_class && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-purple-950 text-purple-300 border border-purple-800">
                      Test Class
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* AST Functions */}
        {functions.length > 0 && (
          <div>
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center space-x-1.5 mb-2">
              <FunctionSquare className="w-3.5 h-3.5 text-emerald-400" />
              <span>Functions & Methods ({functions.length})</span>
            </label>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {functions.map((fn, idx) => (
                <div
                  key={idx}
                  className="bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs flex items-center justify-between"
                >
                  <div className="font-mono text-emerald-300 truncate">
                    {fn.is_async && <span className="text-amber-400 mr-1">async</span>}
                    {fn.name}
                  </div>
                  <div className="flex items-center space-x-2">
                    {fn.is_test_func && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-purple-950 text-purple-300 border border-purple-800">
                        test
                      </span>
                    )}
                    <span className="text-[10px] text-slate-500 font-mono">L{fn.lineno}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* AST Imports */}
        {imports.length > 0 && (
          <div>
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center space-x-1.5 mb-2">
              <PackageCheck className="w-3.5 h-3.5 text-cyan-400" />
              <span>Imports ({imports.length})</span>
            </label>
            <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-1">
              {imports.map((imp, idx) => (
                <span
                  key={idx}
                  className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300"
                >
                  {imp}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Manifest Dependencies */}
        {manifestInfo && (
          <div>
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center space-x-1.5 mb-2">
              <PackageCheck className="w-3.5 h-3.5 text-cyan-400" />
              <span>Manifest ({manifestInfo.manifest_type})</span>
            </label>
            <pre className="font-mono text-[11px] bg-slate-950 border border-slate-800 rounded p-3 text-cyan-300 overflow-x-auto">
              {JSON.stringify(manifestInfo.data, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
