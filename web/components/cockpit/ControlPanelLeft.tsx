"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Table2,
  Code2,
  Plus,
  Trash2,
  Upload,
  FilePlus2,
  Play,
  AlertCircle,
  Sparkles,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import {
  ModelDefinition,
  SolverStatus,
  VarType,
  ObjectiveSense,
  ConstraintSense,
} from "./types";
import {
  duplicateVarPrefixes,
  modelToAlgebraicText,
  modelToLatex,
} from "./mathUtils";
import SectionHeading from "./SectionHeading";
import TooltipBadge from "./TooltipBadge";
import KatexBlock from "./KatexBlock";
import { availableWeight, WeightState } from "./weights";

interface NumericInputProps {
  id?: string;
  name?: string;
  ariaLabel?: string;
  value: number | null | undefined;
  onCommit: (val: number | null) => void;
  allowNull?: boolean;
  disabled?: boolean;
  placeholder?: string;
  title?: string;
  className?: string;
  min?: number;
  max?: number;
}

/**
 * Input numérico con buffer de texto local mientras tiene foco:
 * permite borrar dígitos o empezar a escribir "-" sin forzar 0 en cada tecla.
 */
function NumericInput({
  id,
  name,
  ariaLabel,
  value,
  onCommit,
  allowNull = false,
  disabled = false,
  placeholder,
  title,
  className = "",
  min,
  max,
}: NumericInputProps) {
  const formatProp = (v: number | null | undefined) =>
    v === null || v === undefined || Number.isNaN(v) ? "" : String(v);

  const [draft, setDraft] = useState<string>(() => formatProp(value));
  const [focused, setFocused] = useState<boolean>(false);

  useEffect(() => {
    if (!focused) {
      setDraft(formatProp(value));
    }
  }, [value, focused]);

  const parseDraft = (raw: string): number | null | "incomplete" | "invalid" => {
    const trimmed = raw.trim();
    if (trimmed === "") return allowNull ? null : "incomplete";
    if (trimmed === "-" || trimmed === "." || trimmed === "-." || /[eE][+-]?$/.test(trimmed)) {
      return "incomplete";
    }
    const parsed = Number(trimmed.replace(",", "."));
    if (!Number.isFinite(parsed)) return "invalid";
    let clamped = parsed;
    if (min !== undefined) clamped = Math.max(min, clamped);
    if (max !== undefined) clamped = Math.min(max, clamped);
    return clamped;
  };

  const handleChange = (raw: string) => {
    setDraft(raw);
    const parsed = parseDraft(raw);
    if (typeof parsed === "number") {
      onCommit(parsed);
    }
  };

  const commitOrRevert = () => {
    setFocused(false);
    const parsed = parseDraft(draft);
    if (parsed === null && allowNull) {
      onCommit(null);
      setDraft("");
      return;
    }
    if (typeof parsed === "number") {
      onCommit(parsed);
      setDraft(formatProp(parsed));
      return;
    }
    setDraft(formatProp(value));
  };

  const showDraftWarning = focused && parseDraft(draft) === "invalid";

  return (
    <input
      id={id}
      name={name}
      aria-label={ariaLabel || title}
      type="text"
      inputMode="decimal"
      value={draft}
      disabled={disabled}
      placeholder={placeholder}
      title={title}
      onFocus={() => setFocused(true)}
      onBlur={commitOrRevert}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          setDraft(formatProp(value));
          setFocused(false);
          e.currentTarget.blur();
        } else if (e.key === "Enter") {
          e.preventDefault();
          commitOrRevert();
          e.currentTarget.blur();
        }
      }}
      onChange={(e) => handleChange(e.target.value)}
      className={`${className}${showDraftWarning ? " ring-1 ring-amber-500 border-amber-500" : ""}`}
    />
  );
}

function WeightInput({ index, label, value, disabled, onCommit }: {
  index: number;
  label: string;
  value: number;
  disabled: boolean;
  onCommit: (index: number, value: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const shownValue = String(Number(value.toPrecision(6)));
  const commit = () => {
    if (draft === null) return;
    const entered = draft.trim();
    setDraft(null);
    if (entered === shownValue) return;
    onCommit(index, entered ? Number(entered.replace(",", ".")) : NaN);
  };

  return (
    <input id={"weight-input-" + index} aria-label={"Valor numérico peso " + label} aria-describedby="weight-help"
      type="text" inputMode="decimal" value={draft ?? shownValue} disabled={disabled}
      onChange={event => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={event => {
        if (event.key === "Escape") setDraft(null);
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
        }
      }}
      className="min-h-9 w-28 rounded border border-slate-300 bg-slate-50 px-2 text-right text-sm font-mono dark:border-slate-700 dark:bg-slate-800" />
  );
}

interface ControlPanelLeftProps {
  model: ModelDefinition;
  modelKey: number;
  weightState: WeightState;
  weightError: string;
  onToggleWeight: (index: number) => void;
  onEqualizeWeights: () => void;
  onWeightChange: (index: number, value: number) => void;
  onImportExercise: (file: File) => void;
  onNewBlankModel: () => void;
  validationError: string | null;
  solverStatus: SolverStatus;
  solverMessage: string;
  onMetadataChange: (patch: Partial<Pick<ModelDefinition, "name" | "description" | "reference">>) => void;
  onModelChange: (updated: ModelDefinition, objectiveIndices?: number[]) => boolean;
  algebraicDraft: string | null;
  algebraicErrors: string[];
  onAlgebraicDraftChange: (draft: string | null) => void;
  onApplyAlgebraic: () => boolean;
  onManualSolve: () => void;
  isCalculating: boolean;
  isLoadingExercise: boolean;
}

export default function ControlPanelLeft({
  model,
  modelKey,
  weightState,
  weightError,
  onToggleWeight,
  onEqualizeWeights,
  onWeightChange,
  onImportExercise,
  onNewBlankModel,
  validationError,
  solverStatus,
  solverMessage,
  onMetadataChange,
  onModelChange,
  algebraicDraft,
  algebraicErrors,
  onAlgebraicDraftChange,
  onApplyAlgebraic,
  onManualSolve,
  isCalculating,
  isLoadingExercise,
}: ControlPanelLeftProps) {
  const [editorTab, setEditorTab] = useState<"table" | "algebraic">("table");
  const [openSections, setOpenSections] = useState<{ vars: boolean; objs: boolean; cons: boolean }>({
    vars: true,
    objs: true,
    cons: true,
  });
  const algebraicText = useMemo(() => modelToAlgebraicText(model), [model]);
  const algebraicDirty = algebraicDraft !== null;
  const algebraicErrorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (algebraicErrors.length > 0) algebraicErrorRef.current?.focus();
  }, [algebraicErrors]);

  const latexPreview = useMemo(() => modelToLatex(model), [model]);
  const dupPrefixes = useMemo(
    () => duplicateVarPrefixes(model.variables.map((v) => v.name)),
    [model.variables],
  );
  const varChipLabel = (rawName: string) => {
    const trimmed = rawName.trim();
    const head = trimmed.split(/\s+/)[0];
    return dupPrefixes.has(head) ? trimmed : head;
  };

  const fileInputRef = useRef<HTMLInputElement>(null);
  const { values: weights, fixed } = weightState;
  const freeCount = fixed.filter(value => !value).length;
  const remainingWeight = availableWeight(weightState);
  const weightSum = weights.reduce((total, weight) => total + weight, 0);

  const handleVarChange = (
    idx: number,
    field: "name" | "var_type",
    value: string
  ) => {
    const nextVars = model.variables.map((v, i) => {
      if (i !== idx) return v;
      if (field === "name") return { ...v, name: value };
      const vt = value as VarType;
      return {
        ...v,
        var_type: vt,
        lower_bound: vt === "binary" ? 0 : v.lower_bound,
        upper_bound: vt === "binary" ? 1 : v.upper_bound,
      };
    });
    onModelChange({ ...model, variables: nextVars });
  };

  const handleVarBound = (idx: number, field: "lower_bound" | "upper_bound", val: number | null) => {
    const nextVars = model.variables.map((v, i) => (i === idx ? { ...v, [field]: val } : v));
    onModelChange({ ...model, variables: nextVars });
  };

  const handleAddVariable = () => {
    const existingNames = new Set(model.variables.map((v) => v.name.trim()));
    let nextIdx = model.variables.length + 1;
    while (existingNames.has(`x${nextIdx}`)) {
      nextIdx += 1;
    }
    const nextVars = [
      ...model.variables,
      { name: `x${nextIdx}`, var_type: "continuous" as VarType, lower_bound: 0, upper_bound: null },
    ];
    const nextObjs = model.objectives.map((o) => ({
      ...o,
      coefficients: [...o.coefficients, 0],
    }));
    const nextCons = model.constraints.map((c) => ({
      ...c,
      coefficients: [...c.coefficients, 0],
    }));
    onModelChange({ ...model, variables: nextVars, objectives: nextObjs, constraints: nextCons });
  };

  const handleRemoveVariable = (idx: number) => {
    if (model.variables.length <= 1) return;
    const nextVars = model.variables.filter((_, i) => i !== idx);
    const nextObjs = model.objectives.map((o) => ({
      ...o,
      coefficients: o.coefficients.filter((_, i) => i !== idx),
    }));
    const nextCons = model.constraints.map((c) => ({
      ...c,
      coefficients: c.coefficients.filter((_, i) => i !== idx),
    }));
    onModelChange({ ...model, variables: nextVars, objectives: nextObjs, constraints: nextCons });
  };

  const handleObjField = (idx: number, field: "name" | "sense", value: string) => {
    const nextObjs = model.objectives.map((o, i) =>
      i === idx ? { ...o, [field]: field === "sense" ? (value as ObjectiveSense) : value } : o
    );
    onModelChange({ ...model, objectives: nextObjs });
  };

  const handleObjCoeff = (objIdx: number, varIdx: number, val: number) => {
    const nextObjs = model.objectives.map((o, i) => {
      if (i !== objIdx) return o;
      const nextC = [...o.coefficients];
      nextC[varIdx] = Number.isFinite(val) ? val : 0;
      return { ...o, coefficients: nextC };
    });
    onModelChange({ ...model, objectives: nextObjs });
  };

  const handleAddObjective = () => {
    const nextIdx = model.objectives.length + 1;
    const nextObjs = [
      ...model.objectives,
      {
        name: `Objetivo ${nextIdx}`,
        sense: "maximize" as ObjectiveSense,
        coefficients: Array(model.variables.length).fill(1),
      },
    ];
    onModelChange({ ...model, objectives: nextObjs }, [...model.objectives.map((_, i) => i), -1]);
  };

  const handleRemoveObjective = (idx: number) => {
    if (model.objectives.length <= 2) return;
    const nextObjs = model.objectives.filter((_, i) => i !== idx);
    const indices = model.objectives.map((_, i) => i).filter(i => i !== idx);
    onModelChange({ ...model, objectives: nextObjs }, indices);
  };

  const handleConField = (idx: number, field: "name" | "sense" | "rhs", value: string | number) => {
    const nextCons = model.constraints.map((c, i) => {
      if (i !== idx) return c;
      if (field === "rhs") {
        const num = typeof value === "number" ? value : parseFloat(value);
        return { ...c, rhs: Number.isFinite(num) ? num : 0 };
      }
      if (field === "sense") return { ...c, sense: value as ConstraintSense };
      return { ...c, name: String(value) };
    });
    onModelChange({ ...model, constraints: nextCons });
  };

  const handleConCoeff = (conIdx: number, varIdx: number, val: number) => {
    const nextCons = model.constraints.map((c, i) => {
      if (i !== conIdx) return c;
      const nextC = [...c.coefficients];
      nextC[varIdx] = Number.isFinite(val) ? val : 0;
      return { ...c, coefficients: nextC };
    });
    onModelChange({ ...model, constraints: nextCons });
  };

  const handleAddConstraint = () => {
    const nextIdx = model.constraints.length + 1;
    const nextCons = [
      ...model.constraints,
      {
        name: `Restricción ${nextIdx}`,
        coefficients: Array(model.variables.length).fill(1),
        sense: "<=" as ConstraintSense,
        rhs: 100,
      },
    ];
    onModelChange({ ...model, constraints: nextCons });
  };

  const handleRemoveConstraint = (idx: number) => {
    const nextCons = model.constraints.filter((_, i) => i !== idx);
    onModelChange({ ...model, constraints: nextCons });
  };

  const handleSwitchToTable = () => {
    const invalidBounds = model.variables.some(({ lower_bound, upper_bound }) =>
      lower_bound != null && upper_bound != null && lower_bound > upper_bound);
    if (invalidBounds || onApplyAlgebraic()) setEditorTab("table");
  };

  return (
    <aside className="workspace-controls min-w-0">
      <fieldset className="model-form min-w-0 space-y-4" disabled={isLoadingExercise}>
      <section aria-label="Carga de ejercicios" className="workspace-actions">
        <a href="/plantilla-ejercicio-iad.xlsx" download className="workspace-button">Obtener plantilla (.xlsx)</a>
        <input
          ref={fileInputRef}
          type="file"
          aria-label="Archivo del ejercicio (.xlsx, .json o .csv)"
          accept=".xlsx,.json,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/json,text/csv"
          disabled={algebraicDirty}
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onImportExercise(file);
            event.target.value = "";
          }}
        />
        <button type="button" className="workspace-button" disabled={algebraicDirty}
          title={algebraicDirty ? "Aplica o descarta el borrador primero" : undefined}
          onClick={() => fileInputRef.current?.click()}>
          <Upload size={15} aria-hidden="true" /> Cargar ejercicio
        </button>
        <button type="button" className="workspace-button" disabled={algebraicDirty || isLoadingExercise}
          title={algebraicDirty ? "Aplica o descarta el borrador primero" : "Iniciar un modelo nuevo en blanco"}
          onClick={onNewBlankModel}>
          <FilePlus2 size={15} aria-hidden="true" /> Nuevo modelo
        </button>
        <p>Admite libros Excel (.xlsx) de la carpeta ejercicios/ o la plantilla oficial, además de .csv y .json.</p>
      </section>
      {weightError && <p role="alert" className="workspace-feedback text-rose-800 dark:text-rose-300">{weightError}</p>}
      {/* Encabezado del Modelo */}
      <div className="rounded-sm border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3.5 space-y-2 border-l-4 border-l-[#E11D48]">
        <div className="flex items-center justify-between gap-2">
          <input
            id="model-name-input"
            name="model-name"
            type="text"
            value={model.name}
            readOnly={algebraicDirty} aria-describedby={algebraicDirty ? "metadata-lock" : undefined}
            onChange={(e) => onMetadataChange({ name: e.target.value })}
            aria-label="Nombre del problema"
            placeholder="Nombre del problema"
            className="w-full text-sm font-bold bg-transparent text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-[#E11D48] rounded-sm px-1 -ml-1"
          />
          <button
            type="button"
            onClick={onManualSolve}
            disabled={isLoadingExercise || (!algebraicDirty && (isCalculating || Boolean(validationError)))}
            className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-bold bg-[#E11D48] hover:bg-[#BE123C] text-white disabled:opacity-50 transition-colors"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Resolver</span>
          </button>
        </div>
        <textarea
          id="model-description-input"
          name="model-description"
          rows={2}
          value={model.description || ""}
          readOnly={algebraicDirty} aria-describedby={algebraicDirty ? "metadata-lock" : undefined}
          onChange={(e) => onMetadataChange({ description: e.target.value })}
          aria-label="Descripción del problema"
          placeholder="Descripción opcional del problema de decisión..."
          className="w-full text-[11px] leading-relaxed bg-transparent text-slate-500 dark:text-slate-400 resize-none focus:outline-none focus:ring-1 focus:ring-[#E11D48] rounded-sm px-1 -ml-1"
        />
        <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
          Fuente académica (opcional)
          <input id="model-reference-input" name="model-reference" type="text" value={model.reference ?? ""} readOnly={algebraicDirty} aria-describedby={algebraicDirty ? "metadata-lock" : undefined}
            onChange={e => onMetadataChange({ reference: e.target.value })}
            className="mt-1 block w-full rounded border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
            placeholder="Curso, taller o referencia del ejercicio" />
        </label>
        {algebraicDirty && <p id="metadata-lock" className="text-xs text-amber-900 dark:text-amber-200">
          Aplica o descarta el borrador algebraico para editar el nombre, la descripción y la fuente.
        </p>}
      </div>

      {/* Alerta de Validación Inmediata en Cliente */}
      {validationError && (
        <div role="alert" className="flex items-start gap-2 p-3 rounded-sm bg-rose-50 dark:bg-rose-950/40 border-2 border-[#E11D48] text-xs text-rose-900 dark:text-rose-200">
          <AlertCircle className="w-4 h-4 text-[#E11D48] shrink-0 mt-0.5" />
          <div className="space-y-1.5">
            <div>
              <span className="font-bold block">Error de Validación del Modelo:</span>
              <span>{validationError}</span>
            </div>
          </div>
        </div>
      )}

      {/* Editor del Modelo con Pestañas (Tabla / Algebraico) — Primero se define el problema */}
      <section
        id="cockpit-model-editor"
        className="rounded-sm border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden"
      >
        <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-3 py-2 bg-slate-50 dark:bg-slate-900">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleSwitchToTable}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-semibold transition-colors ${
                editorTab === "table"
                  ? "bg-[#E11D48] text-white"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
              }`}
            >
              <Table2 className="w-3.5 h-3.5" />
              <span>Modo Tabla</span>
            </button>
            <button
              type="button"
              onClick={() => setEditorTab("algebraic")}
              disabled={isLoadingExercise}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-semibold transition-colors ${
                editorTab === "algebraic"
                  ? "bg-[#E11D48] text-white"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>Modo Algebraico</span>
            </button>
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            {model.variables.length}v · {model.objectives.length}obj · {model.constraints.length}res
          </span>
        </div>

        <div className="p-3.5 space-y-4">
          {editorTab === "table" ? (
            <>
              {algebraicDirty && (
                <div className="workspace-feedback flex flex-wrap items-center justify-between gap-2 text-amber-900 dark:text-amber-200">
                  <span>El borrador sigue pendiente. Puedes corregir el tipo y las cotas de las variables. Edita las ecuaciones en Modo Algebraico.</span>
                  <div className="flex flex-wrap gap-1.5">
                    <button type="button" onClick={() => setEditorTab("algebraic")} className="workspace-button text-xs">
                      Ir a Modo Algebraico
                    </button>
                    <button type="button" onClick={() => onAlgebraicDraftChange(null)} className="workspace-button text-xs">
                      Descartar borrador
                    </button>
                  </div>
                </div>
              )}
              {/* 1. Variables de Decisión (Acordeón sin scroll anidado) */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      aria-expanded={openSections.vars}
                      onClick={() => setOpenSections((s) => ({ ...s, vars: !s.vars }))}
                      className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 hover:text-[#E11D48] cursor-pointer"
                    >
                      {openSections.vars ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      <span>Variables ({model.variables.length})</span>
                    </button>
                    <TooltipBadge
                      title="Variables (LP y MIP)"
                      content="Soporta variables Continuas (ℝ), Enteras (ℤ) y Binarias ({0,1}) resueltas con HiGHS y ramificación y poda en el motor."
                    />
                  </div>
                  <button
                    type="button"
                    disabled={algebraicDirty}
                    onClick={() => {
                      setOpenSections((s) => ({ ...s, vars: true }));
                      handleAddVariable();
                    }}
                    className="inline-flex items-center gap-1 text-[11px] font-bold text-[#E11D48] hover:underline cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Añadir
                  </button>
                </div>

                <p className="section-cue">Define qué cantidades decidir y sus límites posibles.</p>
                {openSections.vars && (
                <div className="space-y-1.5">
                  <div className="grid grid-cols-[1.8fr_1.1fr_0.75fr_0.75fr_24px] gap-1.5 px-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    <span>Variable (Descripción)</span>
                    <span>Tipo</span>
                    <span className="text-right">Mín</span>
                    <span className="text-right">Máx</span>
                    <span />
                  </div>
                  {model.variables.map((v, idx) => (
                    <div
                      key={idx}
                      className="grid grid-cols-[1.8fr_1.1fr_0.75fr_0.75fr_24px] gap-1.5 items-center bg-slate-50 dark:bg-slate-800/60 p-1.5 rounded-sm border border-slate-200 dark:border-slate-700/60"
                    >
                      <input
                        id={`var-name-${idx}`}
                        name={`var-name-${idx}`}
                        aria-label={`Nombre de variable ${idx + 1}`}
                        type="text"
                        value={v.name}
                        title={v.name}
                        disabled={algebraicDirty}
                        onChange={(e) => handleVarChange(idx, "name", e.target.value)}
                        className="text-xs font-mono px-1.5 py-1 rounded-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 focus:outline-[#E11D48] min-w-0"
                        placeholder="x1 (Nombre)"
                      />
                      <select
                        id={`var-type-${idx}`}
                        name={`var-type-${idx}`}
                        aria-label={`Tipo de variable ${v.name || idx + 1}`}
                        value={v.var_type}
                        onChange={(e) => handleVarChange(idx, "var_type", e.target.value)}
                        className="text-[11px] px-1 py-1 rounded-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 focus:outline-[#E11D48] min-w-0"
                      >
                        <option value="continuous">Continua</option>
                        <option value="integer">Entera</option>
                        <option value="binary">Binaria</option>
                      </select>
                      <NumericInput
                        id={`var-lb-${idx}`}
                        name={`var-lb-${idx}`}
                        ariaLabel={`Cota inferior de ${v.name || `variable ${idx + 1}`}`}
                        value={v.lower_bound}
                        allowNull={true}
                        onCommit={(val) => handleVarBound(idx, "lower_bound", val)}
                        disabled={v.var_type === "binary"}
                        placeholder="-∞"
                        title="Cota inferior (vacío = -∞)"
                        className="text-xs font-mono text-right px-1 py-1 rounded-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 disabled:opacity-50 focus:outline-[#E11D48] min-w-0"
                      />
                      <NumericInput
                        id={`var-ub-${idx}`}
                        name={`var-ub-${idx}`}
                        ariaLabel={`Cota superior de ${v.name || `variable ${idx + 1}`}`}
                        value={v.upper_bound}
                        allowNull={true}
                        onCommit={(val) => handleVarBound(idx, "upper_bound", val)}
                        disabled={v.var_type === "binary"}
                        placeholder="+∞"
                        title="Cota superior (vacío = +∞)"
                        className="text-xs font-mono text-right px-1 py-1 rounded-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 disabled:opacity-50 focus:outline-[#E11D48] min-w-0"
                      />
                      <button
                        type="button"
                        onClick={() => handleRemoveVariable(idx)}
                        disabled={algebraicDirty || model.variables.length <= 1}
                        className="flex justify-center text-slate-400 hover:text-[#E11D48] disabled:opacity-30 cursor-pointer"
                        title="Eliminar variable"
                        aria-label={`Eliminar variable ${v.name || idx + 1}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
                )}
              </div>

              {/* 2. Funciones Objetivo */}
              <fieldset disabled={algebraicDirty} className="min-w-0 space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800 disabled:opacity-70">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      aria-expanded={openSections.objs}
                      onClick={() => setOpenSections((s) => ({ ...s, objs: !s.objs }))}
                      className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 hover:text-[#E11D48] cursor-pointer"
                    >
                      {openSections.objs ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      <span>Funciones Objetivo ({model.objectives.length})</span>
                    </button>
                    <TooltipBadge
                      title="Funciones Objetivo (Zᵢ)"
                      content="Define al menos 2 criterios en conflicto (Max o Min) con sus coeficientes lineales por variable. Pulsa '+ Añadir' para 3 o más objetivos (gráfico 3D y Radar)."
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setOpenSections((s) => ({ ...s, objs: true }));
                      handleAddObjective();
                    }}
                    className="inline-flex items-center gap-1 text-[11px] font-bold text-[#E11D48] hover:underline cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Añadir
                  </button>
                </div>

                <p className="section-cue">Indica qué deseas maximizar o minimizar y cuánto aporta cada variable.</p>
                {openSections.objs && (
                <div className="space-y-2">
                  {model.objectives.map((obj, oIdx) => (
                    <div
                      key={oIdx}
                      className="p-2 rounded-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 space-y-1.5"
                    >
                      <div className="flex items-center gap-1.5">
                        <select
                          id={`obj-sense-${oIdx}`}
                          name={`obj-sense-${oIdx}`}
                          aria-label={`Sentido del objetivo ${oIdx + 1}`}
                          value={obj.sense}
                          onChange={(e) => handleObjField(oIdx, "sense", e.target.value)}
                          className={`text-[11px] font-bold px-1.5 py-1 rounded-sm border ${
                            obj.sense === "maximize"
                              ? "bg-[#111524] text-white border-[#111524]"
                              : "bg-rose-50 dark:bg-rose-950/50 text-[#E11D48] dark:text-rose-400 border-rose-200 dark:border-rose-800"
                          }`}
                        >
                          <option value="maximize">Max</option>
                          <option value="minimize">Min</option>
                        </select>
                        <input
                          id={`obj-name-${oIdx}`}
                          name={`obj-name-${oIdx}`}
                          aria-label={`Nombre del objetivo ${oIdx + 1}`}
                          type="text"
                          value={obj.name}
                          onChange={(e) => handleObjField(oIdx, "name", e.target.value)}
                          className="flex-1 text-xs font-medium px-2 py-1 rounded-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100"
                        />
                        <button
                          type="button"
                          onClick={() => handleRemoveObjective(oIdx)}
                          disabled={model.objectives.length <= 2}
                          className="text-slate-400 hover:text-[#E11D48] disabled:opacity-30 cursor-pointer"
                          title="Eliminar objetivo"
                          aria-label={`Eliminar objetivo ${obj.name || oIdx + 1}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="flex flex-wrap gap-1.5">
                        {model.variables.map((v, vIdx) => (
                          <label
                            key={vIdx}
                            htmlFor={`obj-${oIdx}-var-${vIdx}`}
                            className="flex items-center gap-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-sm px-1.5 py-0.5"
                          >
                            <span className="text-[10px] font-mono text-slate-400" title={v.name}>
                              {varChipLabel(v.name)}:
                            </span>
                            <NumericInput
                              id={`obj-${oIdx}-var-${vIdx}`}
                              name={`obj-${oIdx}-var-${vIdx}`}
                              ariaLabel={`Coeficiente de ${v.name} en objetivo ${obj.name || oIdx + 1}`}
                              value={obj.coefficients[vIdx] ?? 0}
                              onCommit={(val) => handleObjCoeff(oIdx, vIdx, val ?? 0)}
                              className="w-14 text-right font-mono text-[11px] bg-transparent text-slate-800 dark:text-slate-100 focus:outline-none"
                            />
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                )}
              </fieldset>

              {/* 3. Restricciones */}
              <fieldset disabled={algebraicDirty} className="min-w-0 space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800 disabled:opacity-70">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      aria-expanded={openSections.cons}
                      onClick={() => setOpenSections((s) => ({ ...s, cons: !s.cons }))}
                      className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 hover:text-[#E11D48] cursor-pointer"
                    >
                      {openSections.cons ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      <span>Restricciones Lineales ({model.constraints.length})</span>
                    </button>
                    <TooltipBadge
                      title="Restricciones del Sistema"
                      content="Limitan la región factible mediante desigualdades (≤, ≥) o igualdades (=). Asegúrate de que el conjunto factible sea no vacío y acotado."
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setOpenSections((s) => ({ ...s, cons: true }));
                      handleAddConstraint();
                    }}
                    className="inline-flex items-center gap-1 text-[11px] font-bold text-[#E11D48] hover:underline cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Añadir
                  </button>
                </div>

                <p className="section-cue">Representa capacidades, demandas y balances mediante ecuaciones o desigualdades.</p>
                {openSections.cons && (
                <div className="space-y-2">
                  {model.constraints.map((c, cIdx) => (
                    <div
                      key={cIdx}
                      className="p-2 rounded-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 space-y-1.5"
                    >
                      <div className="flex items-center gap-1.5">
                        <input
                          id={`con-name-${cIdx}`}
                          name={`con-name-${cIdx}`}
                          aria-label={`Nombre de restricción ${cIdx + 1}`}
                          type="text"
                          value={c.name}
                          onChange={(e) => handleConField(cIdx, "name", e.target.value)}
                          className="flex-1 text-xs font-medium px-2 py-1 rounded-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100"
                        />
                        <select
                          id={`con-sense-${cIdx}`}
                          name={`con-sense-${cIdx}`}
                          aria-label={`Operador de restricción ${c.name || cIdx + 1}`}
                          value={c.sense}
                          onChange={(e) => handleConField(cIdx, "sense", e.target.value)}
                          className="text-xs font-mono font-bold px-1.5 py-1 rounded-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-[#E11D48]"
                        >
                          <option value="<=">≤</option>
                          <option value=">=">≥</option>
                          <option value="==">=</option>
                        </select>
                        <NumericInput
                          id={`con-rhs-${cIdx}`}
                          name={`con-rhs-${cIdx}`}
                          ariaLabel={`Lado derecho de restricción ${c.name || cIdx + 1}`}
                          value={c.rhs}
                          onCommit={(val) => handleConField(cIdx, "rhs", val ?? 0)}
                          className="w-20 text-right font-mono text-xs px-1.5 py-1 rounded-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100"
                        />
                        <button
                          type="button"
                          onClick={() => handleRemoveConstraint(cIdx)}
                          className="text-slate-400 hover:text-[#E11D48]"
                          title="Eliminar restricción"
                          aria-label={`Eliminar restricción ${c.name || cIdx + 1}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="flex flex-wrap gap-1.5">
                        {model.variables.map((v, vIdx) => (
                          <label
                            key={vIdx}
                            htmlFor={`con-${cIdx}-var-${vIdx}`}
                            className="flex items-center gap-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-sm px-1.5 py-0.5"
                          >
                            <span className="text-[10px] font-mono text-slate-400" title={v.name}>
                              {varChipLabel(v.name)}:
                            </span>
                            <NumericInput
                              id={`con-${cIdx}-var-${vIdx}`}
                              name={`con-${cIdx}-var-${vIdx}`}
                              ariaLabel={`Coeficiente de ${v.name} en restricción ${c.name || cIdx + 1}`}
                              value={c.coefficients[vIdx] ?? 0}
                              onCommit={(val) => handleConCoeff(cIdx, vIdx, val ?? 0)}
                              className="w-12 text-right font-mono text-[11px] bg-transparent text-slate-800 dark:text-slate-100 focus:outline-none"
                            />
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                )}
              </fieldset>
            </>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <label htmlFor="algebraic-model-textarea" className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">
                    Ecuaciones del modelo (Max/Min Z = ..., s.a., ≤ / ≥ / =)
                  </label>
                  {algebraicDirty && (
                    <button
                      type="button"
                      onClick={() => onAlgebraicDraftChange(null)}
                      className="text-[10px] font-semibold text-amber-600 dark:text-amber-400 hover:underline"
                    >
                      Descartar borrador
                    </button>
                  )}
                </div>
                <p className="section-cue">Edita las ecuaciones lineales. Los tipos y las cotas se editan en Modo Tabla.</p>
                <textarea
                  id="algebraic-model-textarea"
                  name="algebraic-model"
                  rows={8}
                  value={algebraicDraft ?? algebraicText}
                  readOnly={isLoadingExercise}
                  onChange={(e) => onAlgebraicDraftChange(e.target.value === algebraicText ? null : e.target.value)}
                  aria-label="Ecuaciones del modelo"
                  aria-invalid={algebraicErrors.length > 0}
                  aria-describedby={algebraicErrors.length > 0 ? "algebraic-feedback" : undefined}
                  spellCheck={false}
                  className="w-full font-mono text-xs p-2.5 rounded-sm border bg-slate-50 dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-[#E11D48]"
                />
                {algebraicDirty && (
                  <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
                    Resolver y cambiar de vista aplican las ecuaciones. Descarta el borrador para abrir otro ejercicio.
                  </p>
                )}
              </div>

              {algebraicErrors.length > 0 && (
                <div ref={algebraicErrorRef} id="algebraic-feedback" role="alert" tabIndex={-1} className="p-2.5 rounded-sm bg-rose-500/10 border border-rose-500/30 text-xs text-rose-800 dark:text-rose-200 space-y-1">
                  <div className="font-bold flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5" />
                    <span>Revisa el borrador algebraico</span>
                  </div>
                  <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                    {algebraicErrors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}

              {!algebraicDirty && !validationError && ["error", "infeasible", "unbounded"].includes(solverStatus) && (
                <p role="alert" className="p-2.5 rounded-sm bg-rose-500/10 border border-rose-500/30 text-xs text-rose-800 dark:text-rose-200">
                  {solverMessage}
                </p>
              )}

              <button
                type="button"
                onClick={onManualSolve}
                disabled={isLoadingExercise || (!algebraicDirty && (isCalculating || Boolean(validationError)))}
                className="w-full inline-flex items-center justify-center gap-1.5 py-2 rounded-sm text-xs font-bold bg-[#E11D48] hover:bg-[#BE123C] text-white transition-colors"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Aplicar Ecuaciones y Resolver</span>
              </button>
            </div>
          )}

          {/* Vista Previa Matemática en LaTeX siempre disponible para Tabla y Algebraico */}
          <div className="pt-3 border-t border-slate-100 dark:border-slate-800">
            <div className="rounded-sm border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/70 p-3 space-y-1.5">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Vista Previa Matemática (LaTeX / KaTeX)
              </div>
              <p className="section-cue">
                {algebraicDirty ? "Esta vista muestra el modelo aplicado. El borrador está en el editor."
                  : "Comprueba las ecuaciones y dominios que recibe el motor."}
              </p>
              <KatexBlock
                latex={latexPreview}
                className="text-xs text-slate-800 dark:text-slate-200"
              />
            </div>
          </div>
        </div>
      </section>

      </fieldset>

      <a href="#grafico-resultados" className="mobile-plot-link inline-block text-xs font-semibold text-rose-800 underline underline-offset-2 dark:text-rose-300 min-[851px]:hidden">
        Ir al gráfico
      </a>
      <section id="cockpit-weights-panel"
        className="rounded-sm border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3.5 space-y-3">
        <SectionHeading title="Preferencias" cue="Ajusta los pesos de los objetivos." />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs font-mono font-semibold text-emerald-800 dark:text-emerald-300">
              Σw = {weightSum.toFixed(3)}
            </span>
            {fixed.some(Boolean) && (
              <span className="rounded border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 px-2 py-1 text-[11px] font-mono text-slate-700 dark:text-slate-200">
                Disponible: {remainingWeight.toFixed(3)}
              </span>
            )}
          </div>
          <button type="button" className="workspace-button" disabled={isLoadingExercise} onClick={onEqualizeWeights}>Igualar pesos</button>
        </div>
        <p id="weight-help" className="text-xs text-slate-600 dark:text-slate-300">
          {freeCount === 0 ? "Todos los pesos están fijados. Desbloquea un peso con 📌."
            : freeCount === 1 ? "El único peso libre completa la suma de 1. Desbloquea otro para ajustarlo."
            : remainingWeight <= 0 ? "Los pesos fijados ya suman 1. Desbloquea alguno para ajustar los demás."
            : "Fija con 📌 los valores que quieras conservar. Los demás se ajustan para sumar 1."}
        </p>
        {weightError && <p role="alert" className="text-xs font-medium text-rose-800 dark:text-rose-300">{weightError}</p>}
        <div className="space-y-3" key={modelKey}>
          {model.objectives.map((obj, idx) => {
            const value = weights[idx];
            const locked = fixed[idx];
            const disabled = isLoadingExercise || locked || freeCount < 2 || remainingWeight <= 0;
            return (
              <div key={idx} className="space-y-1">
                <label htmlFor={`weight-input-${idx}`} className="block break-words text-xs font-medium text-slate-700 dark:text-slate-200">
                  <span className="font-mono font-bold text-rose-700 dark:text-rose-300 mr-1">w{idx + 1}</span>{obj.name}
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <WeightInput index={idx} label={obj.name} value={value} disabled={disabled} onCommit={onWeightChange} />
                  <button
                    type="button"
                    aria-label={`Fijar peso de ${obj.name}`}
                    aria-pressed={locked}
                    disabled={isLoadingExercise}
                    className="workspace-button weight-pin"
                    onClick={() => onToggleWeight(idx)}
                  >
                    <span aria-hidden="true">📌</span> {locked ? "Desbloquear" : "Fijar peso"}
                  </button>
                </div>
                <input
                  id={`weight-slider-${idx}`}
                  aria-label={`Ajustar peso de ${obj.name}`}
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={value}
                  disabled={disabled}
                  onChange={(event) => onWeightChange(idx, Math.min(remainingWeight, event.currentTarget.valueAsNumber))}
                  className="w-full weight-slider bg-slate-200 dark:bg-slate-700"
                />
              </div>
            );
          })}
        </div>

        {/* Leyenda rápida de métricas con tooltips */}
        <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2 text-[11px]">
          <div className="flex items-center gap-1 text-blue-600 dark:text-blue-400 font-semibold">
            <span className="w-2 h-2 rounded-xs bg-[#2563EB]" />
            <span>L₁</span>
            <TooltipBadge
              title="Métrica L₁ (Compensatoria / Manhattan)"
              content="Minimiza la suma ponderada de desviaciones. Permite compensación total: sacrificar mucho un objetivo si otro mejora más."
            />
          </div>
          <div className="flex items-center gap-1 text-slate-700 dark:text-slate-300 font-semibold">
            <span className="w-2 h-2 rounded-xs bg-[#334155] dark:bg-slate-300" />
            <span>L₂</span>
            <TooltipBadge
              title="Métrica L₂ (Euclidiana)"
              content="Eleva al cuadrado cada brecha ya ponderada y minimiza la suma. La distancia mostrada incluye la raíz cuadrada."
              align="center"
            />
          </div>
          <div className="flex items-center gap-1 text-[#E11D48] font-semibold">
            <span className="w-2 h-2 rounded-xs bg-[#E11D48]" />
            <span>L∞</span>
            <TooltipBadge
              title="Métrica L∞ (Equilibrio Minimax / Tchebysheff)"
              content="Minimiza la mayor desviación ponderada (λ). Las restricciones activas comparten ese valor."
              align="right"
            />
          </div>
        </div>
        {model.objectives.length > 3 && (
          <label htmlFor="pareto-seed-input" className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-700 dark:text-slate-300">
            Semilla de la frontera
            <NumericInput
              id="pareto-seed-input"
              name="pareto-seed"
              ariaLabel="Semilla de la frontera"
              min={0}
              max={4294967295}
              value={model.pareto_seed ?? 42}
              onCommit={(val) => {
                const nextSeed = val === null ? 42 : Math.round(val);
                if (
                  Number.isInteger(nextSeed) &&
                  nextSeed >= 0 &&
                  nextSeed <= 4294967295 &&
                  nextSeed !== (model.pareto_seed ?? 42)
                ) {
                  onModelChange({ ...model, pareto_seed: nextSeed });
                }
              }}
              className="w-28 rounded border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700"
            />
          </label>
        )}
      </section>
    </aside>
  );
}
