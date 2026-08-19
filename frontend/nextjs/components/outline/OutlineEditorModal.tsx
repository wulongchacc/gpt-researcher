"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

import type { ModelProfile, OutlineSection } from "../../types/data";
import {
  MAX_OUTLINE_SECTIONS,
  MIN_OUTLINE_SECTIONS,
  addOutlineSection,
  canConfirmOutline,
  moveOutlineSection,
  normalizeOutlineSections,
  removeOutlineSection,
  updateOutlineSection,
  validateOutlineSections,
} from "./outlineEditor";

interface OutlineEditorModalProps {
  open: boolean;
  task: string;
  initialSections: OutlineSection[];
  modelProfile: ModelProfile;
  onCancel: () => void;
  onConfirm: (sections: OutlineSection[]) => void;
}

const createSectionId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `section-${Date.now()}-${Math.random().toString(16).slice(2)}`;

const IconButton = ({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) => (
  <button
    type="button"
    aria-label={label}
    title={label}
    disabled={disabled}
    onClick={onClick}
    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-gray-700 bg-gray-900 text-gray-300 transition-colors hover:border-teal-500/60 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
  >
    {children}
  </button>
);

export default function OutlineEditorModal({
  open,
  task,
  initialSections,
  modelProfile,
  onCancel,
  onConfirm,
}: OutlineEditorModalProps) {
  const [mounted, setMounted] = useState(false);
  const [sections, setSections] = useState<OutlineSection[]>(initialSections);
  const [validationError, setValidationError] = useState<string | null>(null);
  const minSections = MIN_OUTLINE_SECTIONS;
  const maxSections = modelProfile === "simple"
    ? MIN_OUTLINE_SECTIONS
    : MAX_OUTLINE_SECTIONS;

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    setSections(initialSections.map((section) => ({ ...section })));
    setValidationError(null);
  }, [initialSections, open]);

  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleEscape);
    };
  }, [onCancel, open]);

  if (!mounted || !open) return null;

  const updateSection = (
    sectionId: string,
    changes: Partial<Pick<OutlineSection, "title" | "description">>,
  ) => {
    setSections((current) => updateOutlineSection(current, sectionId, changes));
    setValidationError(null);
  };

  const confirmOutline = () => {
    const error = validateOutlineSections(sections, minSections, maxSections);
    if (error) {
      setValidationError(error);
      return;
    }
    onConfirm(normalizeOutlineSections(sections));
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/75 p-3 backdrop-blur-sm sm:p-6"
      role="presentation"
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="outline-editor-title"
        className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-gray-700 bg-[#101827] shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-gray-800 px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <h2 id="outline-editor-title" className="text-lg font-semibold text-white">
              确认研究提纲
            </h2>
            <p className="mt-1 line-clamp-2 text-sm text-gray-400">{task}</p>
          </div>
          <IconButton label="关闭提纲编辑器" onClick={onCancel}>
            <span aria-hidden="true" className="text-xl leading-none">×</span>
          </IconButton>
        </header>

        <div className="overflow-y-auto px-4 py-4 sm:px-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-gray-300">
              {modelProfile === "simple"
                ? `确认 3 个章节后再开始研究`
                : `调整章节后再开始深度研究（${minSections}–${maxSections} 章）`}
            </p>
            <span className="text-xs font-medium text-teal-300">
              {sections.length}/{maxSections}
            </span>
          </div>

          <ol className="space-y-3">
            {sections.map((section, index) => (
              <li
                key={section.id}
                className="grid gap-3 rounded-md border border-gray-700 bg-gray-900/65 p-3 sm:grid-cols-[2.25rem_minmax(0,1fr)_auto] sm:p-4"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-teal-950 text-sm font-semibold text-teal-300">
                  {index + 1}
                </div>

                <div className="min-w-0 space-y-3">
                  <div>
                    <label htmlFor={`outline-title-${section.id}`} className="mb-1 block text-xs font-medium text-gray-400">
                      章节标题
                    </label>
                    <input
                      id={`outline-title-${section.id}`}
                      value={section.title}
                      maxLength={80}
                      onChange={(event) => updateSection(section.id, { title: event.target.value })}
                      className="h-10 w-full rounded-md border border-gray-700 bg-[#0c111f] px-3 text-sm text-white outline-none transition-colors placeholder:text-gray-600 focus:border-teal-500 focus:ring-1 focus:ring-teal-500"
                      placeholder="输入章节标题"
                    />
                  </div>
                  <div>
                    <label htmlFor={`outline-description-${section.id}`} className="mb-1 block text-xs font-medium text-gray-400">
                      研究重点
                    </label>
                    <textarea
                      id={`outline-description-${section.id}`}
                      value={section.description}
                      maxLength={240}
                      rows={2}
                      onChange={(event) => updateSection(section.id, { description: event.target.value })}
                      className="min-h-20 w-full resize-y rounded-md border border-gray-700 bg-[#0c111f] px-3 py-2 text-sm text-white outline-none transition-colors placeholder:text-gray-600 focus:border-teal-500 focus:ring-1 focus:ring-teal-500"
                      placeholder="说明本章需要回答的问题"
                    />
                  </div>
                </div>

                <div className="flex gap-2 sm:flex-col">
                  <IconButton
                    label={`上移第 ${index + 1} 章`}
                    disabled={index === 0}
                    onClick={() => setSections((current) => moveOutlineSection(current, index, -1))}
                  >
                    <span aria-hidden="true">↑</span>
                  </IconButton>
                  <IconButton
                    label={`下移第 ${index + 1} 章`}
                    disabled={index === sections.length - 1}
                    onClick={() => setSections((current) => moveOutlineSection(current, index, 1))}
                  >
                    <span aria-hidden="true">↓</span>
                  </IconButton>
                  <IconButton
                    label={`删除第 ${index + 1} 章`}
                    disabled={sections.length <= minSections}
                    onClick={() => setSections((current) => removeOutlineSection(current, section.id, minSections))}
                  >
                    <span aria-hidden="true" className="text-lg leading-none">−</span>
                  </IconButton>
                </div>
              </li>
            ))}
          </ol>

          <button
            type="button"
            disabled={sections.length >= maxSections}
            onClick={() => setSections((current) => addOutlineSection(current, createSectionId, maxSections))}
            className="mt-4 flex h-10 items-center gap-2 rounded-md border border-dashed border-gray-600 px-4 text-sm font-medium text-gray-300 transition-colors hover:border-teal-500 hover:text-teal-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <span aria-hidden="true" className="text-lg leading-none">+</span>
            添加章节
          </button>

          {validationError && (
            <p role="alert" className="mt-4 rounded-md border border-red-900/70 bg-red-950/50 px-3 py-2 text-sm text-red-300">
              {validationError}
            </p>
          )}
        </div>

        <footer className="flex flex-col-reverse gap-3 border-t border-gray-800 bg-gray-950/45 px-4 py-4 sm:flex-row sm:justify-end sm:px-6">
          <button
            type="button"
            onClick={onCancel}
            className="h-11 rounded-md border border-gray-700 px-5 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800 hover:text-white"
          >
            取消
          </button>
          <button
            type="button"
            disabled={!canConfirmOutline(sections, minSections, maxSections)}
            onClick={confirmOutline}
            className="h-11 rounded-md bg-teal-600 px-6 text-sm font-semibold text-white transition-colors hover:bg-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:cursor-not-allowed disabled:bg-gray-700 disabled:text-gray-400"
          >
            确认并开始研究
          </button>
        </footer>
      </section>
    </div>,
    document.body,
  );
}
