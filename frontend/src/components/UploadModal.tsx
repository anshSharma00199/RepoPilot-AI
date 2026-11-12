"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, X, AlertOctagon, CheckCircle2, Loader2, ShieldAlert } from "lucide-react";
import { uploadRepository } from "../lib/api";
import { Repository, ApiError } from "../lib/types";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (repo: Repository) => void;
}

export function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file: File) => {
    setError(null);
    if (!file.name.toLowerCase().endsWith(".zip")) {
      setError({
        error_code: "INVALID_FILE_TYPE",
        message: "Only ZIP archives are supported.",
      });
      setSelectedFile(null);
      return;
    }
    // 50 MB client-side sanity limit
    if (file.size > 50 * 1024 * 1024) {
      setError({
        error_code: "FILE_TOO_LARGE",
        message: `File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds 50 MB limit.`,
      });
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const handleSubmit = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    setError(null);

    try {
      const repo = await uploadRepository(selectedFile);
      setIsUploading(false);
      onSuccess(repo);
      onClose();
    } catch (err: any) {
      setIsUploading(false);
      if (err.error_code && err.message) {
        setError(err);
      } else {
        setError({
          error_code: "UPLOAD_FAILED",
          message: err.message || "Failed to upload repository archive.",
        });
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div>
            <h2 className="text-lg font-semibold text-white">Ingest Repository Archive</h2>
            <p className="text-xs text-slate-400">Upload a software repository ZIP to scan and inventory</p>
          </div>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {/* Dropzone */}
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition flex flex-col items-center justify-center ${
              dragActive
                ? "border-blue-500 bg-blue-950/20"
                : selectedFile
                ? "border-emerald-600 bg-emerald-950/10"
                : "border-slate-700 hover:border-slate-600 bg-slate-950/50"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".zip"
              className="hidden"
              onChange={handleFileChange}
              disabled={isUploading}
            />

            {selectedFile ? (
              <div className="flex flex-col items-center space-y-2">
                <CheckCircle2 className="w-12 h-12 text-emerald-400" />
                <div className="text-sm font-medium text-white">{selectedFile.name}</div>
                <div className="text-xs text-slate-400">
                  {(selectedFile.size / 1024).toFixed(1)} KB — Ready to upload
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center space-y-2">
                <UploadCloud className="w-12 h-12 text-slate-400" />
                <div className="text-sm font-medium text-slate-300">
                  Drag and drop your repository ZIP here, or{" "}
                  <span className="text-blue-400 hover:underline">browse</span>
                </div>
                <div className="text-xs text-slate-500">
                  Supports .zip archives up to 50 MB. Code is safely inspected without execution.
                </div>
              </div>
            )}
          </div>

          {/* Security Features Notice */}
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 text-xs text-slate-400 flex items-start space-x-2">
            <ShieldAlert className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
            <div>
              <span className="font-semibold text-slate-300">Safety Guardrails Active: </span>
              Validates archive headers, blocks path traversals (<code className="text-slate-300">..</code>), prevents zip bombs, neutralizes symlinks, and performs non-executing AST parsing.
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-rose-950/50 border border-rose-800/80 rounded-xl p-4 text-xs text-rose-300 flex items-start space-x-3">
              <AlertOctagon className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-rose-200">
                  Security / Ingestion Error: {error.error_code}
                </div>
                <div className="mt-1">{error.message}</div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end px-6 py-4 border-t border-slate-800 bg-slate-950/40 space-x-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isUploading}
            className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-white rounded-lg transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!selectedFile || isUploading}
            className={`px-5 py-2 text-sm font-medium rounded-lg shadow-sm flex items-center space-x-2 transition ${
              !selectedFile || isUploading
                ? "bg-blue-600/50 text-blue-200 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-500 text-white"
            }`}
          >
            {isUploading && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{isUploading ? "Uploading & Analyzing..." : "Upload & Analyze"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
