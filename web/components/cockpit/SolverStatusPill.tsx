"use client";

import React from "react";
import {
  CheckCircle2,
  AlertOctagon,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { SolverStatus } from "./types";

interface SolverStatusPillProps {
  solverStatus: SolverStatus;
  solverMessage: string;
  hasDraft: boolean;
}

/** Indicador compacto del estado del modelo y del motor de optimización. */
export default function SolverStatusPill({
  solverStatus,
  solverMessage,
  hasDraft,
}: SolverStatusPillProps) {
  if (hasDraft) {
    return (
      <span
        className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-amber-500/40 bg-amber-500/15 px-2.5 py-1 text-xs font-semibold text-amber-900 dark:text-amber-200"
        title="Aplica o descarta las ecuaciones pendientes"
      >
        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
        <span>Borrador sin aplicar</span>
      </span>
    );
  }

  switch (solverStatus) {
    case "optimal":
      return (
        <div
          title={solverMessage}
          className="inline-flex items-center gap-1.5 whitespace-nowrap px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 border border-emerald-500/40"
        >
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          <span>Óptimo</span>
        </div>
      );
    case "partial":
      return (
        <span
          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-amber-500/40 bg-amber-500/15 px-2.5 py-1 text-xs font-semibold text-amber-900 dark:text-amber-200"
          title={solverMessage}
        >
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>Resultado parcial</span>
        </span>
      );
    case "infeasible":
      return (
        <div
          title={solverMessage}
          className="inline-flex items-center gap-1.5 whitespace-nowrap px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-800 dark:text-rose-300 border border-rose-500/40"
        >
          <AlertOctagon className="w-3.5 h-3.5 shrink-0" />
          <span>Infactible</span>
        </div>
      );
    case "unbounded":
      return (
        <div
          title={solverMessage}
          className="inline-flex items-center gap-1.5 whitespace-nowrap px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-900 dark:text-amber-200 border border-amber-500/40"
        >
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>No acotado</span>
        </div>
      );
    case "calculating":
      return (
        <div className="inline-flex items-center gap-1.5 whitespace-nowrap px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-900 dark:text-amber-200 border border-amber-500/40">
          <Loader2 className="w-3.5 h-3.5 shrink-0 animate-spin" />
          <span>Calculando...</span>
        </div>
      );
    case "error":
      return (
        <div
          title={solverMessage}
          className="inline-flex items-center gap-1.5 whitespace-nowrap px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-800 dark:text-rose-300 border border-rose-500/40"
        >
          <AlertOctagon className="w-3.5 h-3.5 shrink-0" />
          <span>Error</span>
        </div>
      );
    default:
      return (
        <div className="inline-flex items-center gap-1.5 whitespace-nowrap px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/15 text-slate-700 dark:text-slate-300 border border-slate-500/30">
          <span>Listo</span>
        </div>
      );
  }
}
