"use client";

import { useEffect, useRef, useState } from "react";
import { FileSpreadsheet, FileText } from "lucide-react";
import CopyForReport from "./CopyForReport";
import type { ModelDefinition, SolveResponse } from "./types";

interface ResultDownloadsProps {
  model: ModelDefinition;
  result: SolveResponse;
  axes2d: [number, number];
  axes3d: [number, number, number];
  disabled: boolean;
}

type ExportFormat = "excel" | "pdf";

export default function ResultDownloads({ model, result, axes2d, axes3d, disabled }: ResultDownloadsProps) {
  const inProgress = useRef<AbortController | null>(null);
  const [format, setFormat] = useState<ExportFormat | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);

  useEffect(() => {
    setMessage("");
    setError(false);
    setFormat(null);
    return () => {
      inProgress.current?.abort();
      inProgress.current = null;
    };
  }, [model, result, disabled]);

  const download = async (target: ExportFormat) => {
    if (disabled || inProgress.current) return;
    const controller = new AbortController();
    inProgress.current = controller;
    setFormat(target);
    setMessage("");
    setError(false);

    try {
      const { renderReportCharts } = await import("./reportCharts");
      const { charts, warnings } = await renderReportCharts(model, result, axes2d, axes3d, controller.signal);
      if (controller.signal.aborted) return;
      if (!charts.length) throw new Error(warnings.join(" ") || "No se generaron las gráficas de este ejercicio.");
      const reportResult = { ...result, weight_sensitivity: undefined };
      const response = await fetch(`/api/export/${target}`, {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: { ...model, weights: result.weights }, result: reportResult, charts, warnings }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(typeof detail?.detail === "string" ? detail.detail : `El servidor devolvió HTTP ${response.status}.`);
      }

      const blob = await response.blob();
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      const filename = model.name.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        .toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "modelo";
      const link = document.createElement("a");
      link.href = url;
      link.download = `OptiCompromise_${filename}.${target === "excel" ? "xlsx" : "pdf"}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage(warnings.length ? `Exportación con gráficas pendientes. ${warnings.join(" ")}`
        : `Archivo generado con ${charts.length} gráficas.`);
    } catch (cause) {
      if (controller.signal.aborted) return;
      setError(true);
      setMessage(`No se pudo generar el archivo. ${cause instanceof Error ? cause.message : "Vuelve a intentarlo."}`);
    } finally {
      if (inProgress.current === controller) {
        inProgress.current = null;
        setFormat(null);
      }
    }
  };

  return (
    <div className="report-actions min-w-0" role="group" aria-label="Salidas del informe">
      <div className="flex flex-wrap items-start gap-1.5 sm:gap-2">
        <CopyForReport model={model} result={result} disabled={disabled} />
        <button type="button" disabled={disabled || format !== null} className="workspace-button" onClick={() => void download("excel")}>
          <FileSpreadsheet size={15} aria-hidden="true" /> Excel (.xlsx)
        </button>
        <button type="button" disabled={disabled || format !== null} className="workspace-button" onClick={() => void download("pdf")}>
          <FileText size={15} aria-hidden="true" /> PDF
        </button>
      </div>
      <div role="status" className={`text-xs ${error ? "text-rose-800 dark:text-rose-300" : "text-slate-600 dark:text-slate-300"}`}>
        {(format || message) && (
          <p className="mt-2">{format ? `Generando ${format === "excel" ? "Excel" : "PDF"} y gráficas…` : message}</p>
        )}
      </div>
    </div>
  );
}
