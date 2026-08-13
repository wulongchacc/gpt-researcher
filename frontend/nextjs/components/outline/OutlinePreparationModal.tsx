"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface OutlinePreparationModalProps {
  open: boolean;
  task: string;
  status: "loading" | "error";
  errorMessage?: string;
  onCancel: () => void;
  onRetry: () => void;
}

export default function OutlinePreparationModal({
  open,
  task,
  status,
  errorMessage,
  onCancel,
  onRetry,
}: OutlinePreparationModalProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  if (!mounted || !open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[1090] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="outline-preparation-title"
        className="w-full max-w-lg rounded-lg border border-gray-700 bg-[#101827] shadow-2xl"
      >
        <div className="px-5 py-5 sm:px-6">
          <div className="flex items-start gap-4">
            {status === "loading" ? (
              <div
                className="mt-0.5 h-9 w-9 shrink-0 animate-spin rounded-full border-2 border-gray-700 border-t-teal-400"
                aria-hidden="true"
              />
            ) : (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-red-950 text-lg font-semibold text-red-300">
                <span aria-hidden="true">!</span>
              </div>
            )}

            <div className="min-w-0">
              <h2 id="outline-preparation-title" className="text-lg font-semibold text-white">
                {status === "loading" ? "正在生成研究提纲" : "提纲生成失败"}
              </h2>
              <p className="mt-1 line-clamp-2 text-sm text-gray-400">{task}</p>
              {status === "loading" ? (
                <p className="mt-4 text-sm text-gray-300">
                  正在分析研究主题并规划 3–5 个章节，请稍候。
                </p>
              ) : (
                <p role="alert" className="mt-4 rounded-md border border-red-900/70 bg-red-950/40 px-3 py-2 text-sm text-red-300">
                  {errorMessage || "生成提纲时发生错误，请重试。"}
                </p>
              )}
            </div>
          </div>
        </div>

        <footer className="flex flex-col-reverse gap-3 border-t border-gray-800 px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
          <button
            type="button"
            onClick={onCancel}
            className="h-10 rounded-md border border-gray-700 px-4 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800 hover:text-white"
          >
            {status === "loading" ? "取消生成" : "返回修改"}
          </button>
          {status === "error" && (
            <button
              type="button"
              onClick={onRetry}
              className="h-10 rounded-md bg-teal-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              重新生成
            </button>
          )}
        </footer>
      </section>
    </div>,
    document.body,
  );
}
