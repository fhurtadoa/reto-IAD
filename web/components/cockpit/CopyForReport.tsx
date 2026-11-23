"use client";

import { useEffect, useRef, useState } from "react";
import { Copy } from "lucide-react";
import { buildNumericReport } from "./numericReport";
import type { ModelDefinition, SolveResponse } from "./types";

export default function CopyForReport({ model, result, disabled }: {
  model: ModelDefinition;
  result: SolveResponse;
  disabled: boolean;
}) {
  const [feedback, setFeedback] = useState<{ result: SolveResponse; manualText?: string } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeOperation = useRef<AbortController | null>(null);
  const manualInput = useRef<HTMLTextAreaElement>(null);
  const currentFeedback = !disabled && feedback?.result === result ? feedback : null;
  const manualText = currentFeedback?.manualText;

  useEffect(() => {
    setFeedback(null);
    return () => {
      activeOperation.current?.abort();
      if (timer.current) clearTimeout(timer.current);
    };
  }, [model, result, disabled]);

  useEffect(() => {
    if (manualText) {
      manualInput.current?.focus();
      manualInput.current?.select();
    }
  }, [manualText]);

  const copy = async () => {
    if (disabled) return;
    if (timer.current) clearTimeout(timer.current);
    activeOperation.current?.abort();
    const operation = new AbortController();
    activeOperation.current = operation;
    const { markdown, html } = buildNumericReport(model, result);
    try {
      const clipboard = navigator.clipboard;
      if (clipboard?.write && typeof ClipboardItem === "function") {
        try {
          await clipboard.write([new ClipboardItem({
            "text/plain": new Blob([markdown], { type: "text/plain" }),
            "text/html": new Blob([html], { type: "text/html" }),
          })]);
        } catch {
          if (operation.signal.aborted) return;
          await clipboard.writeText(markdown);
        }
      } else {
        await clipboard.writeText(markdown);
      }
      if (operation.signal.aborted) return;
      setFeedback({ result });
      timer.current = setTimeout(() => setFeedback(null), 2200);
    } catch {
      if (!operation.signal.aborted) setFeedback({ result, manualText: markdown });
    }
  };

  return (
    <div className={manualText ? "w-full" : "min-w-0"}>
      <button type="button" className="workspace-button" disabled={disabled} onClick={() => void copy()}>
        <Copy size={15} aria-hidden="true" /> Copiar para informe
      </button>
      <div role="status" className="text-xs text-slate-700 dark:text-slate-200">
        {currentFeedback && !manualText && <p className="mt-2">¡Copiado!</p>}
      </div>
      {manualText && (
        <label className="mt-2 block text-xs text-slate-700 dark:text-slate-200">
          El navegador no pudo copiar automáticamente. Copia el texto seleccionado.
          <textarea ref={manualInput} readOnly value={manualText} rows={6}
            className="mt-1 block w-full rounded border border-slate-300 bg-transparent p-2 font-mono dark:border-slate-700" />
        </label>
      )}
    </div>
  );
}
