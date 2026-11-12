"use client";

import React, { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  FolderGit2,
  Calendar,
  HardDrive,
  Trash2,
  RefreshCw,
  Beaker,
  FileText,
  AlertTriangle,
  Loader2,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { MetricsCards, formatBytes } from "@/components/MetricsCards";
import { SearchFilterBar } from "@/components/SearchFilterBar";
import { FileExplorer } from "@/components/FileExplorer";
import { FileDetailDrawer } from "@/components/FileDetailDrawer";
import { ExecutionPanel } from "@/components/ExecutionPanel";
import { StatusBadge, ClassificationBadge } from "@/components/StatusBadge";
import { UploadModal } from "@/components/UploadModal";
import { AnalysisAuditModal } from "@/components/AnalysisAuditModal";
import {
  fetchRepository,
  fetchRepositoryTree,
  fetchRepositoryFiles,
  fetchFileDetails,
  deleteRepository,
  fetchRepositoryAnalysisAudit,
} from "@/lib/api";
import {
  RepositoryDetail,
  FileTreeNode,
  RepositoryFile,
  Repository,
  AnalysisAuditSummary,
} from "@/lib/types";

export default function RepositoryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const repoId = params.id as string;

  const [repo, setRepo] = useState<RepositoryDetail | null>(null);
  const [tree, setTree] = useState<FileTreeNode | null>(null);
  const [files, setFiles] = useState<RepositoryFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inspector & modal states
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<RepositoryFile | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [audit, setAudit] = useState<AnalysisAuditSummary | null>(null);
  const [isAuditOpen, setIsAuditOpen] = useState(false);

  // Filters & View Mode
  const [search, setSearch] = useState("");
  const [classification, setClassification] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [parseErrorsOnly, setParseErrorsOnly] = useState(false);
  const [viewMode, setViewMode] = useState<"tree" | "list">("tree");

  const loadRepositoryData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [repoData, treeData, filesData, auditData] = await Promise.all([
        fetchRepository(repoId),
        fetchRepositoryTree(repoId),
        fetchRepositoryFiles(repoId, { page_size: 200 }),
        fetchRepositoryAnalysisAudit(repoId).catch(() => null),
      ]);

      setRepo(repoData);
      setTree(treeData);
      setFiles(filesData.items);
      setAudit(auditData);
    } catch (err: any) {
      setError(err.message || "Failed to load repository details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (repoId) {
      loadRepositoryData();
    }
  }, [repoId]);

  // Load single file details for the drawer
  const handleSelectFile = async (fileId: string) => {
    setSelectedFileId(fileId);
    try {
      const details = await fetchFileDetails(repoId, fileId);
      setSelectedFile(details);
    } catch (err) {
      console.error("Failed to load file details", err);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this repository and all inventoried metadata?")) return;
    try {
      await deleteRepository(repoId);
      router.push("/");
    } catch {
      alert("Failed to delete repository.");
    }
  };

  // Filtered files for List View
  const filteredFiles = useMemo(() => {
    return files.filter((f) => {
      if (search && !f.relative_path.toLowerCase().includes(search.toLowerCase())) {
        return false;
      }
      if (classification && f.classification !== classification) {
        return false;
      }
      if (statusFilter && f.status !== statusFilter) {
        return false;
      }
      if (parseErrorsOnly) {
        const hasErr = Boolean(f.ast_metadata?.syntax_error);
        if (!hasErr) return false;
      }
      return true;
    });
  }, [files, search, classification, statusFilter, parseErrorsOnly]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col">
        <Navbar onOpenUpload={() => setIsUploadOpen(true)} />
        <div className="flex-1 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
          <span className="text-sm text-slate-400">Loading repository inventory and tree...</span>
        </div>
      </div>
    );
  }

  if (error || !repo) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col">
        <Navbar onOpenUpload={() => setIsUploadOpen(true)} />
        <div className="flex-1 max-w-xl mx-auto px-4 py-16 flex flex-col items-center text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-rose-950/60 border border-rose-800 flex items-center justify-center text-rose-400">
            <AlertTriangle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-white">Repository Not Found or Failed to Load</h2>
          <p className="text-sm text-slate-400">{error}</p>
          <Link
            href="/"
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold rounded-lg transition"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const scan = repo.latest_scan;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Navigation Breadcrumb & Actions */}
        <div className="flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center space-x-1.5 text-xs text-slate-400 hover:text-white transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Repositories</span>
          </Link>

          <div className="flex items-center space-x-2">
            <button
              onClick={loadRepositoryData}
              className="p-1.5 text-slate-400 hover:text-white bg-slate-900 border border-slate-800 rounded-lg transition"
              title="Refresh Inventory"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={handleDelete}
              className="p-1.5 text-slate-400 hover:text-rose-400 bg-slate-900 border border-slate-800 rounded-lg transition"
              title="Delete Repository"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Repository Header Card */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1.5">
              <div className="flex items-center space-x-3">
                <FolderGit2 className="w-6 h-6 text-blue-400" />
                <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">{repo.name}</h1>
                <StatusBadge status={repo.status} />
              </div>
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
                <div className="flex items-center space-x-1">
                  <HardDrive className="w-3.5 h-3.5 text-slate-500" />
                  <span>{repo.original_filename} ({formatBytes(repo.upload_size_bytes)})</span>
                </div>
                <div className="flex items-center space-x-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-500" />
                  <span>Uploaded {new Date(repo.created_at).toLocaleString()}</span>
                </div>
              </div>
            </div>

            {/* Test Frameworks & Manifest Badges */}
            {scan && (
              <div className="flex flex-wrap items-center gap-2">
                {scan.detected_frameworks.map((fw) => (
                  <span
                    key={fw}
                    className="inline-flex items-center space-x-1 px-3 py-1 rounded-full text-xs font-semibold bg-purple-950/80 text-purple-300 border border-purple-800 shadow-sm"
                  >
                    <Beaker className="w-3.5 h-3.5" />
                    <span>Framework: {fw}</span>
                  </span>
                ))}
                {scan.detected_manifests.map((mf) => (
                  <span
                    key={mf}
                    className="inline-flex items-center space-x-1 px-3 py-1 rounded-full text-xs font-semibold bg-cyan-950/80 text-cyan-300 border border-cyan-800 shadow-sm"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>{mf}</span>
                  </span>
                ))}
                <button
                  onClick={() => setIsAuditOpen(true)}
                  className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-950/80 text-blue-300 border border-blue-800 shadow-sm hover:bg-blue-900 transition"
                  title="View Repository Analysis Audit & Coverage Summary"
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Coverage Audit: {audit ? `${audit.content_analysis_coverage_pct}%` : "View"}</span>
                </button>
              </div>
            )}
          </div>

          {/* Rollup Metrics */}
          <MetricsCards scan={scan} />
        </div>

        {/* Real Baseline Test Execution & Evidence Capture Panel */}
        <ExecutionPanel key={repoId} repositoryId={repoId} />

        {/* Filter Bar */}
        <SearchFilterBar
          search={search}
          onSearchChange={setSearch}
          classification={classification}
          onClassificationChange={setClassification}
          status={statusFilter}
          onStatusChange={setStatusFilter}
          parseErrorsOnly={parseErrorsOnly}
          onParseErrorsOnlyChange={setParseErrorsOnly}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
        />

        {/* File Explorer (Tree vs List) */}
        {viewMode === "tree" ? (
          <div>
            {tree && (
              <FileExplorer
                tree={tree}
                onSelectFile={handleSelectFile}
                selectedFileId={selectedFileId}
              />
            )}
          </div>
        ) : (
          /* List / Table View */
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-[11px] uppercase font-semibold text-slate-400 tracking-wider">
                  <tr>
                    <th className="px-4 py-3">File Path</th>
                    <th className="px-4 py-3">Classification</th>
                    <th className="px-4 py-3">Language</th>
                    <th className="px-4 py-3">Size</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Skip / Error Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {filteredFiles.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500 font-sans">
                        No files match the active filters.
                      </td>
                    </tr>
                  ) : (
                    filteredFiles.map((f) => (
                      <tr
                        key={f.id}
                        onClick={() => handleSelectFile(f.id)}
                        className={`hover:bg-slate-800/60 cursor-pointer transition ${
                          f.id === selectedFileId ? "bg-blue-950/40" : ""
                        }`}
                      >
                        <td className="px-4 py-2.5 font-medium text-slate-200 flex items-center space-x-2">
                          {f.ast_metadata?.syntax_error && (
                            <AlertTriangle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
                          )}
                          <span className="truncate max-w-sm">{f.relative_path}</span>
                        </td>
                        <td className="px-4 py-2.5 font-sans">
                          <ClassificationBadge classification={f.classification} />
                        </td>
                        <td className="px-4 py-2.5 font-sans capitalize">{f.language}</td>
                        <td className="px-4 py-2.5">{formatBytes(f.file_size_bytes)}</td>
                        <td className="px-4 py-2.5 font-sans">
                          <StatusBadge status={f.status} />
                        </td>
                        <td className="px-4 py-2.5 font-sans text-slate-400 text-[11px] truncate max-w-xs">
                          {f.skip_reason || "—"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* File Detail Inspector Drawer */}
      <FileDetailDrawer
        file={selectedFile}
        onClose={() => {
          setSelectedFile(null);
          setSelectedFileId(null);
        }}
      />

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={(newRepo) => {
          router.push(`/repositories/${newRepo.id}`);
        }}
      />

      <AnalysisAuditModal
        audit={audit}
        isOpen={isAuditOpen}
        onClose={() => setIsAuditOpen(false)}
      />
    </div>
  );
}
