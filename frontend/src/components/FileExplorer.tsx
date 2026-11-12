"use client";

import React, { useState } from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  AlertTriangle,
  Beaker,
  FileArchive,
  FileMinus,
} from "lucide-react";
import { FileTreeNode } from "../lib/types";
import { formatBytes } from "./MetricsCards";

interface FileExplorerProps {
  tree: FileTreeNode;
  onSelectFile: (fileId: string) => void;
  selectedFileId?: string | null;
}

interface TreeNodeItemProps {
  node: FileTreeNode;
  depth: number;
  onSelectFile: (fileId: string) => void;
  selectedFileId?: string | null;
}

function TreeNodeItem({ node, depth, onSelectFile, selectedFileId }: TreeNodeItemProps) {
  const [isOpen, setIsOpen] = useState(depth === 0 || depth <= 1);
  const isDir = node.entry_type === "directory";
  const isSelected = node.file_id === selectedFileId;
  const isSkipped = node.status === "skipped";

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isDir) {
      setIsOpen(!isOpen);
    } else if (node.file_id) {
      onSelectFile(node.file_id);
    }
  };

  const getFileIcon = () => {
    if (node.has_syntax_error) {
      return <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />;
    }
    if (node.is_test) {
      return <Beaker className="w-4 h-4 text-purple-400 flex-shrink-0" />;
    }
    if (node.is_manifest) {
      return <FileArchive className="w-4 h-4 text-cyan-400 flex-shrink-0" />;
    }
    if (isSkipped) {
      return <FileMinus className="w-4 h-4 text-amber-400 flex-shrink-0" />;
    }
    if (node.classification === "documentation") {
      return <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />;
    }
    return <FileCode className="w-4 h-4 text-blue-400 flex-shrink-0" />;
  };

  return (
    <div>
      <div
        onClick={handleToggle}
        style={{ paddingLeft: `${depth * 18 + 10}px` }}
        className={`group flex items-center justify-between py-1.5 pr-3 text-xs cursor-pointer select-none border-b border-slate-900/40 hover:bg-slate-800/60 transition ${
          isSelected
            ? "bg-blue-950/60 text-blue-300 font-medium border-l-2 border-l-blue-500"
            : isSkipped
            ? "text-slate-500 hover:text-slate-400"
            : "text-slate-300 hover:text-white"
        }`}
      >
        <div className="flex items-center space-x-2 truncate">
          {/* Chevron for directories */}
          {isDir ? (
            <span className="p-0.5 rounded text-slate-400 hover:text-white">
              {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </span>
          ) : (
            <span className="w-3.5" />
          )}

          {/* Icon */}
          {isDir ? (
            isOpen ? (
              <FolderOpen className="w-4 h-4 text-amber-400 flex-shrink-0" />
            ) : (
              <Folder className="w-4 h-4 text-amber-400 flex-shrink-0" />
            )
          ) : (
            getFileIcon()
          )}

          {/* Node Name */}
          <span className={`truncate font-mono ${node.has_syntax_error ? "text-rose-300" : ""}`}>
            {node.name}
          </span>
        </div>

        {/* Right side indicators */}
        <div className="flex items-center space-x-2 flex-shrink-0">
          {node.has_syntax_error && (
            <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-rose-950 text-rose-300 border border-rose-800">
              Syntax Error
            </span>
          )}
          {node.is_test && (
            <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-purple-950 text-purple-300 border border-purple-800">
              Test
            </span>
          )}
          {node.is_manifest && (
            <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-cyan-950 text-cyan-300 border border-cyan-800">
              Manifest
            </span>
          )}
          {isSkipped && (
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-amber-950/80 text-amber-400 border border-amber-900">
              Skipped
            </span>
          )}
          {!isDir && node.file_size_bytes > 0 && (
            <span className="text-[11px] font-mono text-slate-500">
              {formatBytes(node.file_size_bytes)}
            </span>
          )}
        </div>
      </div>

      {/* Children */}
      {isDir && isOpen && node.children && node.children.length > 0 && (
        <div>
          {node.children.map((child, idx) => (
            <TreeNodeItem
              key={`${child.relative_path}-${idx}`}
              node={child}
              depth={depth + 1}
              onSelectFile={onSelectFile}
              selectedFileId={selectedFileId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileExplorer({ tree, onSelectFile, selectedFileId }: FileExplorerProps) {
  if (!tree || (!tree.children || tree.children.length === 0)) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-400 text-sm">
        No files in repository inventory.
      </div>
    );
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <div className="px-4 py-2.5 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider">
        <span>Repository Tree</span>
        <span>Attributes / Size</span>
      </div>
      <div className="max-h-[600px] overflow-y-auto divide-y divide-slate-800/40">
        {tree.children.map((child, idx) => (
          <TreeNodeItem
            key={`${child.relative_path}-${idx}`}
            node={child}
            depth={0}
            onSelectFile={onSelectFile}
            selectedFileId={selectedFileId}
          />
        ))}
      </div>
    </div>
  );
}
