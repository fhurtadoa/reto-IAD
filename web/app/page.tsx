"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { BookOpen, ChartNoAxesCombined, ChevronUp, FlaskConical, ListChecks } from "lucide-react";
import TopBar from "../components/cockpit/TopBar";
import SolverStatusPill from "../components/cockpit/SolverStatusPill";
import ControlPanelLeft from "../components/cockpit/ControlPanelLeft";
import VisualCanvasRight from "../components/cockpit/VisualCanvasRight";
import {
  ModelDefinition,
  SolveResponse,
  SolverStatus,
  ThemeMode,
  BLANK_MODEL,
  FALLBACK_CELDAS_MODEL,
} from "../components/cockpit/types";
import { hasFeasibleSolution, importModelFromFile, parseAlgebraicModel } from "../components/cockpit/mathUtils";
import SectionHeading from "../components/cockpit/SectionHeading";
import { changeWeight, createWeights, equalizeWeights, remapWeights, type WeightState } from "../components/cockpit/weights";

type Workspace = "model" | "method" | "results";
type ExampleSummary = { id: string; label: string; badge: string };
const WORKSPACE_STORAGE = "opticompromise.workspace";

const workspaces = [
  ["model", "Formular", ListChecks, "Formular el ejercicio", "Del enunciado al modelo de decisión"],
  ["method", "Ver método", FlaskConical, "Cómo se calcula el compromiso", "De las referencias a la solución ponderada"],
  ["results", "Explorar resultados", ChartNoAxesCombined, "Explorar resultados", "Compara soluciones y ajusta los pesos"],
] as const;

function validateModelClient(m: ModelDefinition, weightsToCheck?: number[]): string | null {
  if (m.variables.length < 1) return "Agrega al menos 1 variable de decisión.";
  if (m.objectives.length < 2) return "Un problema multiobjetivo requiere al menos 2 objetivos.";
  const seen = new Set<string>();
  for (const v of m.variables) {
    const clean = v.name.trim();
    if (!clean) return "Todas las variables deben tener un nombre no vacío.";
    if (seen.has(clean)) return `Variable duplicada: "${clean}". Cambia el nombre para que sea único.`;
    seen.add(clean);
    if (
      v.lower_bound !== null &&
      v.upper_bound !== null &&
      !Number.isNaN(v.lower_bound) &&
      !Number.isNaN(v.upper_bound) &&
      v.lower_bound > v.upper_bound
    ) {
      return `Cotas inválidas en "${clean}": la cota inferior (${v.lower_bound}) supera la superior (${v.upper_bound}).`;
    }
  }
  for (let i = 0; i < m.objectives.length; i++) {
    if (!m.objectives[i].name.trim()) {
      return `El Objetivo #${i + 1} debe tener un nombre no vacío.`;
    }
  }
  if (m.pareto_seed !== undefined && (!Number.isInteger(m.pareto_seed) || m.pareto_seed < 0 || m.pareto_seed > 4294967295)) {
    return "La semilla de Pareto debe ser un entero entre 0 y 4294967295.";
  }
  if (weightsToCheck) {
    if (weightsToCheck.length !== m.objectives.length || weightsToCheck.some((w) => !Number.isFinite(w) || w < 0 || w > 1)) {
      return "Ingresa un peso entre 0 y 1 por cada objetivo.";
    }
    const sumW = weightsToCheck.reduce((acc, w) => acc + w, 0);
    if (Math.abs(sumW - 1.0) > 0.001 + 1e-12) {
      return `Los pesos deben sumar 1 (actual: ${sumW.toFixed(3)}).`;
    }
  }
  return null;
}

export default function OptiCompromiseCockpitPage() {
  const [theme, setTheme] = useState<ThemeMode>("light");
  useEffect(() => {
    try {
      const savedTheme = window.localStorage.getItem("opticompromise.theme");
      if (savedTheme === "dark" || savedTheme === "light") setTheme(savedTheme);
    } catch { /* Storage may be disabled. */ }
  }, []);
  const [algebraicDraft, setAlgebraicDraft] = useState<string | null>(null);
  const [algebraicErrors, setAlgebraicErrors] = useState<string[]>([]);
  const hasAlgebraicDraft = algebraicDraft !== null;
  const [loadError, setLoadError] = useState("");
  const [reportSlot, setReportSlot] = useState<HTMLDivElement | null>(null);
  const [isLoadingExercise, setIsLoadingExercise] = useState(false);
  const [examplesOpen, setExamplesOpen] = useState(false);
  const [examplesList, setExamplesList] = useState<ExampleSummary[] | null>(null);
  const [examplesBusy, setExamplesBusy] = useState(false);
  const [examplesError, setExamplesError] = useState("");
  const examplesMenuRef = useRef<HTMLDivElement>(null);
  const [modelKey, setModelKey] = useState<number>(0);
  const [model, setModel] = useState<ModelDefinition>(FALLBACK_CELDAS_MODEL);
  const [weightState, setWeightState] = useState(() => createWeights(FALLBACK_CELDAS_MODEL.weights ?? [0.5, 0.5]));
  const [weightError, setWeightError] = useState("");
  const weights = weightState.values;
  const [completed, setCompleted] = useState<{
    model: ModelDefinition;
    requestedWeights: number[];
    result: SolveResponse;
  } | null>(null);
  const [lastValid, setLastValid] = useState<{ model: ModelDefinition; weights: WeightState } | null>(null);
  const [workspace, setWorkspace] = useState<Workspace>("results");
  useEffect(() => {
    let saved: string | null = null;
    try { saved = window.localStorage.getItem(WORKSPACE_STORAGE); } catch { /* Storage may be disabled. */ }
    if (saved === "model" || saved === "method") setWorkspace(saved);
  }, []);

  const navigationRevision = useRef(0);
  const navigate = useCallback((next: Workspace) => {
    navigationRevision.current++;
    setWorkspace(next);
    try { window.localStorage.setItem(WORKSPACE_STORAGE, next); } catch { /* Navigation remains available. */ }
  }, []);
  const solveResult = completed?.result ?? null;
  const [solverStatus, setSolverStatus] = useState<SolverStatus>("idle");
  const [solverMessage, setSolverMessage] = useState<string>("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [modelFailed, setModelFailed] = useState(false);
  const isCurrentResult = !hasAlgebraicDraft && completed?.model === model && completed.requestedWeights === weights
    && (solverStatus === "optimal" || solverStatus === "partial");
  const canRestore = modelFailed && lastValid !== null && (
    JSON.stringify(model) !== JSON.stringify(lastValid.model) ||
    weights.some((value, i) => value !== lastValid.weights.values[i])
  );

  // Pinning an already solved weight does not require a new solver call.
  useEffect(() => {
    if (completed?.model !== model || completed.requestedWeights !== weightState.values) return;
    setLastValid(snapshot => {
      if (!snapshot || snapshot.weights.fixed.every((fixed, i) => fixed === weightState.fixed[i])) return snapshot;
      return { ...snapshot, weights: structuredClone(weightState) };
    });
  }, [completed, model, weightState]);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const presetRequestRef = useRef(0);
  const cancelPending = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    abortRef.current?.abort();
  }, []);

  useEffect(() => () => {
    presetRequestRef.current++;
    cancelPending();
  }, [cancelPending]);

  useEffect(() => {
    if (!examplesOpen) return;
    const onMouseDown = (event: MouseEvent) => {
      if (examplesMenuRef.current && !examplesMenuRef.current.contains(event.target as Node)) {
        setExamplesOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExamplesOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [examplesOpen]);

  // Sincronizar clase 'dark' en <html>
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  // Llamada real al backend FastAPI (/api/solve)
  const executeSolve = useCallback(async (
    modelToSolve: ModelDefinition,
    preferences: WeightState,
    onSuccess?: () => void,
  ) => {
    cancelPending();
    const weightsToUse = preferences.values;
    setModelFailed(false);
    const clientErr = validateModelClient(modelToSolve, weightsToUse);
    if (clientErr) {
      setValidationError(clientErr);
      setModelFailed(true);
      setSolverStatus("error");
      setSolverMessage(clientErr);
      return;
    }
    setValidationError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    setSolverStatus("calculating");

    try {
      const payload: ModelDefinition = {
        name: modelToSolve.name,
        description: modelToSolve.description || "",
        variables: modelToSolve.variables,
        objectives: modelToSolve.objectives,
        constraints: modelToSolve.constraints,
        weights: weightsToUse,
        pareto_seed: modelToSolve.pareto_seed,
        reference: modelToSolve.reference,
      };

      const res = await fetch("/api/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        if (controller.signal.aborted) return;
        setModelFailed(res.status === 400 || res.status === 422);
        const detail = Array.isArray(errData.detail)
          ? errData.detail.map((issue: { loc: string[] }) => `Revisa el campo ${issue.loc.slice(1).join(".")}.`).join(" ")
          : String(errData.detail || "Error en la resolución del modelo.");
        const lower = detail.toLowerCase();
        if (lower.includes("infeasible") || lower.includes("infactible")) {
          setSolverStatus("infeasible");
        } else if (lower.includes("unbounded") || lower.includes("no acotado")) {
          setSolverStatus("unbounded");
        } else {
          setSolverStatus("error");
        }
        setSolverMessage(detail);
        return;
      }

      const data: SolveResponse = await res.json();
      if (controller.signal.aborted) return;
      if (!hasFeasibleSolution(data)) {
        setModelFailed(true);
        setSolverStatus("error");
        setSolverMessage(data.message || "El motor no devolvió una solución factible.");
        return;
      }
      setLastValid(structuredClone({ model: modelToSolve, weights: preferences }));
      setCompleted(previous => ({
        model: modelToSolve,
        requestedWeights: weightsToUse,
        result: previous?.model === modelToSolve && previous.result.weight_sensitivity
          ? { ...data, weight_sensitivity: previous.result.weight_sensitivity }
          : data,
      }));
      setSolverStatus(data.status === "partial" ? "partial" : "optimal");
      setSolverMessage(data.message || "Solución óptima calculada");
      onSuccess?.();
    } catch (err: unknown) {
      if (controller.signal.aborted || (err instanceof Error && err.name === "AbortError")) return;
      setSolverStatus("error");
      setSolverMessage(
        "No se pudo conectar con el motor de optimización FastAPI (/api/solve). Verifica que el servicio backend esté activo."
      );
    }
  }, [cancelPending]);

  // Debounce reactivo para sliders (50ms gracias al caché LRU en backend) o edición (250ms)
  const scheduleSolve = useCallback(
    (nextModel: ModelDefinition, nextWeights: WeightState, delayMs: number) => {
      cancelPending();
      setModelFailed(false);
      setSolverStatus("calculating");
      debounceRef.current = setTimeout(() => {
        void executeSolve(nextModel, nextWeights);
      }, delayMs);
    },
    [cancelPending, executeSolve]
  );

  const openExercise = useCallback((definition: ModelDefinition, preferences: WeightState) => {
    setModel(definition);
    setWeightState(preferences);
    setModelKey(key => key + 1);
    setCompleted(null);
    setLastValid(null);
    setWeightError("");
    setAlgebraicDraft(null);
    setAlgebraicErrors([]);
    setLoadError("");
    void executeSolve(definition, preferences);
  }, [executeSolve]);

  useEffect(() => {
    setIsLoadingExercise(false);
    openExercise(FALLBACK_CELDAS_MODEL, createWeights(FALLBACK_CELDAS_MODEL.weights ?? [0.5, 0.5]));
  }, [openExercise]);

  const handleNewBlankModel = () => {
    if (hasAlgebraicDraft) return;
    presetRequestRef.current++;
    setIsLoadingExercise(false);
    setLoadError("");
    openExercise(BLANK_MODEL, createWeights(BLANK_MODEL.weights ?? [0.5, 0.5]));
    navigate("model");
  };

  const updateDraft = (draft: string | null) => {
    if (draft !== null) navigationRevision.current++;
    setAlgebraicDraft(draft);
    setAlgebraicErrors([]);
    setWeightError("");
  };

  const applyModel = (updated: ModelDefinition, preferences: WeightState, destination?: Workspace) => {
    presetRequestRef.current++;
    setIsLoadingExercise(false);
    setLoadError("");
    setModel(updated);
    setWeightState(preferences);
    setWeightError("");
    const clientErr = validateModelClient(updated, preferences.values);
    setValidationError(clientErr);
    if (clientErr) {
      cancelPending();
      setModelFailed(true);
      setSolverStatus("error");
      setSolverMessage(clientErr);
    } else if (destination) {
      const revision = navigationRevision.current;
      void executeSolve(updated, preferences, () => {
        if (revision === navigationRevision.current) navigate(destination);
      });
    } else {
      scheduleSolve(updated, preferences, 250);
    }
  };

  const handleModelChange = (updated: ModelDefinition, indices?: number[]): boolean => {
    const next = indices ? remapWeights(weightState, indices) : { state: weightState };
    if ("error" in next) {
      setWeightError(next.error);
      return false;
    }
    setAlgebraicErrors([]);
    applyModel(updated, next.state);
    return true;
  };

  const applyAlgebraicDraft = (destination?: Workspace): boolean => {
    if (algebraicDraft === null) return true;
    const parsed = parseAlgebraicModel(algebraicDraft, model);
    if (!parsed.ok || !parsed.detectedVariables || !parsed.objectives || !parsed.constraints) {
      setAlgebraicErrors(parsed.errors);
      return false;
    }
    const updated: ModelDefinition = {
      ...model,
      variables: parsed.detectedVariables.map(name => model.variables.find(variable => variable.name === name)
        ?? { name, var_type: "continuous", lower_bound: 0, upper_bound: null }),
      objectives: parsed.objectives,
      constraints: parsed.constraints,
    };

    const matched = new Set<number>();
    const indices = updated.objectives.map(objective => {
      const index = model.objectives.findIndex((original, i) => original.name === objective.name && !matched.has(i));
      if (index >= 0) matched.add(index);
      return index;
    });
    const sameOrder = indices.length === weights.length && indices.every((index, i) => index === i);
    const next = sameOrder ? { state: weightState } : remapWeights(weightState, indices);
    if ("error" in next) {
      setAlgebraicErrors([next.error]);
      return false;
    }
    const issue = validateModelClient(updated, next.state.values);
    if (issue) {
      setAlgebraicErrors([issue]);
      return false;
    }
    updateDraft(null);
    applyModel(updated, next.state, destination);
    return true;
  };

  const handleManualSolve = () => {
    if (hasAlgebraicDraft) applyAlgebraicDraft("results");
    else applyModel(model, weightState, "results");
  };

  const restoreLastValid = () => {
    if (!lastValid || !canRestore) return;
    const snapshot = structuredClone(lastValid);
    updateDraft(null);
    setModelKey(key => key + 1);
    navigate("model");
    applyModel(snapshot.model, snapshot.weights, "model");
  };

  const handleMetadataChange = (patch: Partial<Pick<ModelDefinition, "name" | "description" | "reference">>) => {
    const applyPatch = (target: ModelDefinition): ModelDefinition => ({ ...target, ...patch });
    const nextModel = applyPatch(model);
    setModel(nextModel);
    setCompleted(prev => (prev && prev.model === model ? { ...prev, model: nextModel } : prev));
    setLastValid(prev => (prev ? { ...prev, model: applyPatch(prev.model) } : prev));
  };

  const handleApplyWeightsVector = (nextWeights: number[]) => {
    if (nextWeights.length !== model.objectives.length) return;
    const nextState = createWeights(nextWeights);
    setWeightError("");
    presetRequestRef.current++;
    setIsLoadingExercise(false);
    setWeightState(nextState);
    scheduleSolve(model, nextState, 50);
  };

  const applyWeights = (next: ReturnType<typeof changeWeight>) => {
    if ("error" in next) {
      setWeightError(next.error);
      return;
    }
    setWeightError("");
    if (next.state === weightState) return;
    presetRequestRef.current++;
    setIsLoadingExercise(false);
    setWeightState(next.state);
    scheduleSolve(model, next.state, 80);
  };

  const handleExportModelJson = () => {
    if (hasAlgebraicDraft) return;
    const payload: ModelDefinition = {
      name: model.name,
      description: model.description || "",
      reference: model.reference,
      variables: model.variables,
      objectives: model.objectives,
      constraints: model.constraints,
      weights,
      pareto_seed: model.pareto_seed,
    };
    const slug = (model.name || "modelo")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "modelo";
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `OptiCompromise_${slug}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleToggleExamples = async () => {
    if (hasAlgebraicDraft || isLoadingExercise) return;
    const nextOpen = !examplesOpen;
    setExamplesOpen(nextOpen);
    if (!nextOpen || examplesList !== null || examplesBusy) return;
    setExamplesBusy(true);
    setExamplesError("");
    try {
      const res = await fetch("/api/examples");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { exercises?: ExampleSummary[] };
      setExamplesList(Array.isArray(data.exercises) ? data.exercises : []);
    } catch {
      setExamplesError("No se pudieron consultar los ejemplos del servidor.");
    } finally {
      setExamplesBusy(false);
    }
  };

  const handleSelectExample = async (exampleId: string) => {
    if (hasAlgebraicDraft || isLoadingExercise) return;
    setExamplesOpen(false);
    const request = ++presetRequestRef.current;
    const revision = ++navigationRevision.current;
    setIsLoadingExercise(true);
    setLoadError("");
    try {
      const res = await fetch(`/api/examples/${encodeURIComponent(exampleId)}`);
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`);
      }
      const loaded = (await res.json()) as ModelDefinition;
      const nextW = loaded.weights && loaded.weights.length === loaded.objectives.length
        ? loaded.weights
        : Array(loaded.objectives.length).fill(1 / loaded.objectives.length);
      const issue = validateModelClient(loaded, nextW);
      if (issue) throw new Error(issue);
      if (request !== presetRequestRef.current) return;
      openExercise(loaded, createWeights(nextW));
      if (revision === navigationRevision.current && workspace === "method") navigate("results");
    } catch (err: unknown) {
      if (request !== presetRequestRef.current) return;
      setLoadError(`No se pudo cargar el ejemplo. ${err instanceof Error ? err.message : "Vuelve a intentarlo."}`);
    } finally {
      if (request === presetRequestRef.current) setIsLoadingExercise(false);
    }
  };

  const handleImportExercise = async (file: File) => {
    if (hasAlgebraicDraft) return;
    const request = ++presetRequestRef.current;
    const revision = ++navigationRevision.current;
    setIsLoadingExercise(true);
    setLoadError("");
    try {
      const { model: parsed, weights: parsedWeights } = await importModelFromFile(file);
      const nextW = parsedWeights ?? Array(parsed.objectives.length).fill(1 / parsed.objectives.length);
      const issue = validateModelClient(parsed, nextW);
      if (issue) throw new Error(issue);
      if (request !== presetRequestRef.current) return;
      openExercise(parsed, createWeights(nextW));
      if (revision === navigationRevision.current) navigate("model");
    } catch (err: unknown) {
      if (request !== presetRequestRef.current) return;
      const message = err instanceof Error ? err.message : "No se pudo abrir el archivo (.xlsx, .json o .csv).";
      setLoadError(`No se pudo importar el ejercicio. ${message}`);
    } finally {
      if (request === presetRequestRef.current) setIsLoadingExercise(false);
    }
  };

  const section = workspaces.find(([id]) => id === workspace);

  return (
    <div className="min-h-screen flex flex-col bg-[#F3F4F8] dark:bg-[#111524] text-slate-900 dark:text-slate-100">
      <TopBar
        theme={theme}
        onToggleTheme={() => setTheme((t) => {
          const next = t === "dark" ? "light" : "dark";
          try { window.localStorage.setItem("opticompromise.theme", next); } catch { /* Storage may be disabled. */ }
          return next;
        })}
      />

      <div className="workspace-shell" data-workspace={workspace ?? undefined}>
        <section className="workspace-intro" aria-labelledby="workspace-title">
          <div>
            <h1 id="workspace-title">{model.name || "Modelo sin título"}</h1>
            {model.description && <p>{model.description}</p>}
            {model.reference && <p className="academic-reference"><strong>Fuente</strong> · {model.reference}</p>}
          </div>
          <dl aria-label="Dimensiones del modelo">
            <div><dt>Variables</dt><dd>{model.variables.length}</dd></div>
            <div><dt>Objetivos</dt><dd>{model.objectives.length}</dd></div>
            <div><dt>Restricciones</dt><dd>{model.constraints.length}</dd></div>
          </dl>
        </section>

        <nav className="workspace-navigation" aria-label="Espacio de trabajo">
          {workspaces.map(([id, label, Icon]) => (
            <button key={id} type="button" aria-current={workspace === id ? "page" : undefined}
              onClick={() => {
                if (id !== "model" && hasAlgebraicDraft) applyAlgebraicDraft(id);
                else navigate(id);
              }}>
              <Icon aria-hidden="true" size={16} />
              {label}
            </button>
          ))}
          <div role="status" className="workspace-status-pill">
            <SolverStatusPill
              solverStatus={solverStatus}
              solverMessage={solverMessage}
              hasDraft={hasAlgebraicDraft}
            />
          </div>
        </nav>

        {section && workspace && <>
          <div className="workspace-section-heading flex flex-wrap items-center justify-between gap-3">
            <SectionHeading id="workspace-section-title" title={section[3]} cue={section[4]} />
            {workspace === "results" && <div ref={setReportSlot} className="min-w-0" />}
            {canRestore && <button type="button" className="workspace-button" onClick={restoreLastValid}>
              Restaurar último modelo válido
            </button>}
          </div>
          {isLoadingExercise && <p role="status" className="workspace-feedback mb-4">Cargando ejercicio…</p>}
          {loadError && <p role="alert" className="workspace-feedback mb-4 text-rose-800 dark:text-rose-300">{loadError}</p>}
          {workspace === "model" && !validationError && ["error", "infeasible", "unbounded"].includes(solverStatus) && (
            <p className="workspace-feedback mb-4 text-rose-800 dark:text-rose-300" role="alert">{solverMessage}</p>
          )}
          <div className="workspace-body">
            <ControlPanelLeft
              model={model}
              modelKey={modelKey}
              algebraicDraft={algebraicDraft}
              algebraicErrors={algebraicErrors}
              onAlgebraicDraftChange={updateDraft}
              onApplyAlgebraic={applyAlgebraicDraft}
              isLoadingExercise={isLoadingExercise}
              weightState={weightState}
              weightError={weightError}
              onToggleWeight={(index) => {
                setWeightError("");
                setWeightState(current => ({ ...current, fixed: current.fixed.map((fixed, i) => i === index ? !fixed : fixed) }));
              }}
              onEqualizeWeights={() => applyWeights(equalizeWeights(weightState))}
              onWeightChange={(index, value) => applyWeights(changeWeight(weightState, index, value))}
              onImportExercise={handleImportExercise}
              onExportModelJson={handleExportModelJson}
              onNewBlankModel={handleNewBlankModel}
              validationError={validationError}
              solverStatus={solverStatus}
              solverMessage={solverMessage}
              onMetadataChange={handleMetadataChange}
              onModelChange={handleModelChange}
              onManualSolve={handleManualSolve}
              isCalculating={solverStatus === "calculating"}
            />

            <VisualCanvasRight
              workspace={workspace}
              reportSlot={reportSlot}
              selectedWeight={completed?.model === model && !validationError ? weights[0] : (solveResult?.weights[0] ?? null)}
              model={completed?.model ?? model}
              modelKey={modelKey}
              solveResult={solveResult}
              isCurrentResult={isCurrentResult}
              solverStatus={solverStatus}
              solverMessage={solverMessage}
              theme={theme}
              onApplyParetoWeights={handleApplyWeightsVector}
            />
          </div>
        </>}

        <footer className="workspace-footer" aria-label="Ayuda y ejemplos">
          <a className="section-cue-link" href="/MANUAL_DE_USUARIO_Y_CASOS_DE_USO_OPTICOMPROMISE.pdf" target="_blank" rel="noopener noreferrer">Manual de usuario</a>
          <a className="section-cue-link" href="/MANUAL_DOCENTE_OPTICOMPROMISE.pdf" target="_blank" rel="noopener noreferrer">Guía docente</a>
          <div ref={examplesMenuRef} className="footer-examples">
            <button
              type="button"
              className="footer-examples-trigger"
              aria-haspopup="menu"
              aria-expanded={examplesOpen}
              disabled={hasAlgebraicDraft || isLoadingExercise}
              title={hasAlgebraicDraft ? "Aplica o descarta el borrador primero" : "Abrir uno de los casos precargados del curso"}
              onClick={() => void handleToggleExamples()}
            >
              <BookOpen size={14} aria-hidden="true" />
              <span>Ejemplos</span>
              <ChevronUp size={13} className={`transition-transform ${examplesOpen ? "rotate-180" : ""}`} aria-hidden="true" />
            </button>
            {examplesOpen && (
              <div role="menu" aria-label="Casos precargados del curso" className="footer-examples-popover">
                <p className="footer-examples-heading">Casos precargados de IAD</p>
                {examplesBusy && <p className="footer-examples-note">Cargando ejemplos…</p>}
                {examplesError && <p role="alert" className="footer-examples-note text-rose-800 dark:text-rose-300">{examplesError}</p>}
                {!examplesBusy && !examplesError && examplesList && examplesList.length === 0 && (
                  <p className="footer-examples-note">No hay ejemplos disponibles.</p>
                )}
                {!examplesBusy && examplesList && examplesList.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="menuitem"
                    className="footer-examples-item"
                    onClick={() => void handleSelectExample(item.id)}
                  >
                    <span className="footer-examples-label">{item.label}</span>
                    <span className="footer-examples-badge">{item.badge}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <span className="footer-authors">Fabián Andrés Hurtado Arango · Oscar David Arango Garcia · IAD UNAL</span>
        </footer>
      </div>
    </div>
  );
}
