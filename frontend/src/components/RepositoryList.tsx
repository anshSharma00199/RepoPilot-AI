"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  FolderGit2,
  Calendar,
  HardDrive,
  Trash2,
  ChevronRight,
  AlertTriangle,
  Beaker,
  FileText,
  Loader2,
} from "lucide-react";
import { Repository } from "../lib/types";
import { StatusBadge } from "./StatusBadge";
import { formatBytes } from "./MetricsCards";
import { deleteRepository } from "../lib/api";

interface RepositoryListProps {
  repositories: Repository[];
  onRefresh: () => void;
  onOpenUpload: () => void;
}

export function RepositoryList({ repositories, onRefresh, onOpenUpload }: RepositoryListProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this repository and its inventory?")) return;

    setDeletingId(id);
    try {
      await deleteRepository(id);
      onRefresh();
    } catch (err) {
      alert("Failed to delete repository");
    } finally {
      setDeletingId(null);
    }
  };

  if (repositories.length === 0) {
    return (
      <div className="bg-slate-900/60 border border-dashed border-slate-800 rounded-2xl p-12 text-center flex flex-col items-center justify-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-slate-800/80 flex items-center justify-center text-slate-400">
          <FolderGit2 className="w-8 h-8 text-blue-400" />
        </div>
        <div className="space-y-1">
          <h3 className="text-lg font-semibold text-white">No Repositories Ingested Yet</h3>
          <p className="text-sm text-slate-400 max-w-md">
            Upload a Python software repository archive (.zip) to recursively scan its directory tree,
            detect test frameworks, parse AST structures, and prepare an inventory.
          </p>
        </div>
        <button
          onClick={onOpenUpload}
          className="mt-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-xl shadow-lg transition"
        >
          Upload First Repository
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {repositories.map((repo) => {
        const scan = repo.latest_scan;
        const hasSyntaxErrors = (scan?.parse_errors ?? 0) > 0;

        return (
          <Link
            key={repo.id}
            href={`/repositories/${repo.id}`}
            className="block group bg-slate-900/90 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 rounded-xl p-5 shadow-sm transition"
          >
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              {/* Left Info */}
              <div className="space-y-2">
                <div className="flex items-center space-x-3">
                  <FolderGit2 className="w-5 h-5 text-blue-400 group-hover:text-blue-300 transition" />
                  <h3 className="text-base font-semibold text-white group-hover:text-blue-300 transition">
                    {repo.name}
                  </h3>
                  <StatusBadge status={repo.status} />
                  {hasSyntaxErrors && (
                    <span className="flex items-center space-x-1 text-xs px-2 py-0.5 rounded-full bg-rose-950/80 text-rose-300 border border-rose-800">
                      <AlertTriangle className="w-3 h-3 text-rose-400" />
                      <span>{scan?.parse_errors} parse errors</span>
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
                  <div className="flex items-center space-x-1">
                    <HardDrive className="w-3.5 h-3.5 text-slate-500" />
                    <span>{repo.original_filename} ({formatBytes(repo.upload_size_bytes)})</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Calendar className="w-3.5 h-3.5 text-slate-500" />
                    <span>{new Date(repo.created_at).toLocaleString()}</span>
                  </div>
                  {scan && (
                    <>
                      <div className="flex items-center space-x-1 text-slate-300 font-medium">
                        <span>{scan.total_files} files</span>
                        <span className="text-slate-600">•</span>
                        <span>{scan.test_files} tests</span>
                        <span className="text-slate-600">•</span>
                        <span>{scan.manifest_files} manifests</span>
                      </div>
                    </>
                  )}
                </div>

                {/* Frameworks & Manifests Badges */}
                {scan && (scan.detected_frameworks.length > 0 || scan.detected_manifests.length > 0) && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    {scan.detected_frameworks.map((fw) => (
                      <span
                        key={fw}
                        className="inline-flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/80"
                      >
                        <Beaker className="w-3 h-3" />
                        <span>{fw}</span>
                      </span>
                    ))}
                    {scan.detected_manifests.map((mf) => (
                      <span
                        key={mf}
                        className="inline-flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800/80"
                      >
                        <FileText className="w-3 h-3" />
                        <span>{mf}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Right Action Buttons */}
              <div className="flex items-center space-x-3 self-end md:self-center">
                <button
                  onClick={(e) => handleDelete(e, repo.id)}
                  disabled={deletingId === repo.id}
                  title="Delete Repository"
                  className="p-2 text-slate-500 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition"
                >
                  {deletingId === repo.id ? (
                    <Loader2 className="w-4 h-4 animate-spin text-rose-400" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </button>
                <div className="flex items-center space-x-1 text-sm font-medium text-blue-400 group-hover:translate-x-1 transition">
                  <span>Inspect</span>
                  <ChevronRight className="w-4 h-4" />
                </div>
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
