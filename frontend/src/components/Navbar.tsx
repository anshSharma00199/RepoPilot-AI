"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Terminal, Upload, Activity, BookOpen } from "lucide-react";
import { checkHealth } from "../lib/api";

interface NavbarProps {
  onOpenUpload: () => void;
}

export function Navbar({ onOpenUpload }: NavbarProps) {
  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);

  useEffect(() => {
    checkHealth()
      .then((res) => setIsBackendOnline(res.status === "healthy"))
      .catch(() => setIsBackendOnline(false));

    const interval = setInterval(() => {
      checkHealth()
        .then((res) => setIsBackendOnline(res.status === "healthy"))
        .catch(() => setIsBackendOnline(false));
    }, 15000);

    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <Link href="/" className="flex items-center space-x-3 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-blue-500/20 group-hover:scale-105 transition">
            <Terminal className="w-5 h-5" />
          </div>
          <div>
            <div className="text-base font-bold text-white tracking-tight flex items-center space-x-1.5">
              <span>RepoPilot</span>
              <span className="text-blue-400 font-mono text-xs bg-blue-950/80 px-1.5 py-0.5 rounded border border-blue-800">
                AI
              </span>
            </div>
            <div className="text-[11px] text-slate-400">Autonomous Software Debugging Platform</div>
          </div>
        </Link>

        {/* Center / Right controls */}
        <div className="flex items-center space-x-4">
          {/* Backend Status indicator */}
          <div className="hidden sm:flex items-center space-x-2 text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg">
            <Activity className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Backend API:</span>
            {isBackendOnline === null ? (
              <span className="text-slate-500">Checking...</span>
            ) : isBackendOnline ? (
              <span className="flex items-center space-x-1.5 text-emerald-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Online (8000)</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1.5 text-rose-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-rose-400"></span>
                <span>Offline</span>
              </span>
            )}
          </div>

          {/* API Docs Link */}
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="hidden md:flex items-center space-x-1 text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-lg hover:bg-slate-800/60 transition"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>FastAPI Docs</span>
          </a>

          {/* Ingest Repository Button */}
          <button
            onClick={onOpenUpload}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-blue-600/20 transition active:scale-95"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload Archive</span>
          </button>
        </div>
      </div>
    </header>
  );
}
