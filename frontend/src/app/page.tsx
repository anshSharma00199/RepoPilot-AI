"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FolderGit2,
  RefreshCw,
  Upload,
  ShieldCheck,
  Cpu,
  Layers,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { Navbar } from "../components/Navbar";
import { RepositoryList } from "../components/RepositoryList";
import { UploadModal } from "../components/UploadModal";
import { fetchRepositories } from "../lib/api";
import { Repository } from "../lib/types";

export default function DashboardPage() {
  const router = useRouter();
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      setError(null);
      const res = await fetchRepositories();
      setRepositories(res.items);
    } catch (err: any) {
      setError(err.message || "Failed to connect to RepoPilot AI backend API.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleUploadSuccess = (newRepo: Repository) => {
    loadData();
    router.push(`/repositories/${newRepo.id}`);
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950">
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Hero Section */}
        <div className="bg-gradient-to-b from-slate-900 to-slate-900/60 border border-slate-800 rounded-3xl p-8 sm:p-10 shadow-xl relative overflow-hidden">
          <div className="max-w-2xl space-y-4 relative z-10">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-950/80 border border-blue-800 text-blue-300 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-blue-400"></span>
              <span>Day 1 — Foundation & Safe Ingestion Engine</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
              AI-Assisted Software Debugging Platform
            </h1>
            <p className="text-sm sm:text-base text-slate-400 leading-relaxed">
              Upload and inventory software repositories securely. RepoPilot analyzes nested directory
              trees, identifies test infrastructure, parses Python AST structures, and discovers manifests
              without executing unvetted code.
            </p>

            <div className="flex flex-wrap items-center gap-4 pt-2">
              <button
                onClick={() => setIsUploadOpen(true)}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-blue-600/30 transition flex items-center space-x-2"
              >
                <Upload className="w-4 h-4" />
                <span>Upload Repository ZIP</span>
              </button>
            </div>
          </div>

          {/* Feature Highlights Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8 pt-8 border-t border-slate-800/80 text-xs">
            <div className="flex items-start space-x-3 text-slate-300">
              <ShieldCheck className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-white block">Archive Safety Guardrails</span>
                Path traversal & bomb rejection, symlink checks, streaming limits.
              </div>
            </div>
            <div className="flex items-start space-x-3 text-slate-300">
              <Cpu className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-white block">Python AST Analysis</span>
                Structural syntax parsing, function/class indexing without code execution.
              </div>
            </div>
            <div className="flex items-start space-x-3 text-slate-300">
              <Layers className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-white block">Test & Manifest Discovery</span>
                Detects pytest, unittest, tox, requirements.txt, and pyproject.toml.
              </div>
            </div>
          </div>
        </div>

        {/* Repository Management Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FolderGit2 className="w-5 h-5 text-blue-400" />
              <h2 className="text-lg font-bold text-white">Ingested Repositories</h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
                {repositories.length}
              </span>
            </div>

            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center space-x-1.5 text-xs text-slate-400 hover:text-white px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg hover:bg-slate-800 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-4 text-xs text-rose-300 flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-rose-200 block mb-1">Backend Connection Error</span>
                <span>{error} Make sure the FastAPI service is running on http://127.0.0.1:8000.</span>
              </div>
            </div>
          )}

          {/* Loading Skeleton */}
          {loading ? (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 flex flex-col items-center justify-center space-y-3">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
              <span className="text-sm text-slate-400">Loading repositories from backend...</span>
            </div>
          ) : (
            <RepositoryList
              repositories={repositories}
              onRefresh={loadData}
              onOpenUpload={() => setIsUploadOpen(true)}
            />
          )}
        </div>
      </main>

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
}
