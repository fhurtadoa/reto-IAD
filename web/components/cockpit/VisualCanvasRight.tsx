"use client";

import React, { useState, useMemo, useEffect } from "react";
import dynamic from "next/dynamic";
import {
  Box,
  Compass,
  Download,
  Grid,
  ChevronDown,
  ChevronUp,
  AlertOctagon,
  Loader2,
  Target,
} from "lucide-react";
import {
  ModelDefinition,
  SolveResponse,
  SolverStatus,
  ThemeMode,
} from "./types";
import { fmtAchievement, fmtNum } from "./mathUtils";
import { decisionPlot, objectivePlot2D, objectivePlot3D, radarPlot, validParetoPoints } from "./resultFigures";
import ResultDownloads from "./ResultDownloads";
import { createPortal } from "react-dom";
import { sensitivityCurves, sensitivityLayout, sensitivitySelection } from "./weightSensitivity";
import MethodGuide from "./MethodGuide";
import SectionHeading from "./SectionHeading";

const plotConfig = {
  displayModeBar: true,
  responsive: true,
  displaylogo: false,
  modeBarButtonsToRemove: ["sendDataToCloud", "toImage", "select2d", "lasso2d"],
};
const sensitivityConfig = { displayModeBar: false, responsive: true };

let plotComponentPromise: ReturnType<typeof createPlotLoader> | null = null;
async function createPlotLoader() {
  const [{ default: createPlot }, { default: plotly }] = await Promise.all([
    import("react-plotly.js/factory"),
    import("plotly.js-dist-min"),
  ]);
  return createPlot(plotly);
}
function loadPlotComponent() {
  if (!plotComponentPromise) plotComponentPromise = createPlotLoader();
  return plotComponentPromise;
}
if (typeof window !== "undefined") {
  void loadPlotComponent();
}

const Plot = dynamic(loadPlotComponent, {
  ssr: false,
  loading: () => (
    <div className="h-[380px] w-full flex items-center justify-center bg-slate-100 dark:bg-slate-900/50 text-slate-400 text-xs rounded-sm font-mono">
      Inicializando motor gráfico Plotly...
    </div>
  ),
});

interface VisualCanvasRightProps {
  workspace: "model" | "results" | "method";
  model: ModelDefinition;
  modelKey: number;
  selectedWeight: number | null;
  reportSlot: HTMLDivElement | null;
  solveResult: SolveResponse | null;
  isCurrentResult: boolean;
  solverStatus: SolverStatus;
  solverMessage: string;
  theme: ThemeMode;
  onApplyParetoWeights?: (weights: number[]) => void;
}

type ChartTab = "objectives2d" | "objectives3d" | "radar" | "decision2d" | "sensitivity";

export default function VisualCanvasRight({
  workspace,
  model,
  modelKey,
  selectedWeight,
  reportSlot,
  solveResult,
  isCurrentResult,
  solverStatus,
  solverMessage,
  theme,
  onApplyParetoWeights,
}: VisualCanvasRightProps) {
  const [chartTab, setChartTab] = useState<ChartTab>("objectives2d");
  const [pngError, setPngError] = useState<string>("");
  const [isExportingPng, setIsExportingPng] = useState<boolean>(false);
  const [showIsodistance, setShowIsodistance] = useState<boolean>(false);
  const [showPareto, setShowPareto] = useState<boolean>(true);
  const [showFeasibleObj, setShowFeasibleObj] = useState<boolean>(true);
  const [paretoExplorerOpen, setParetoExplorerOpen] = useState<boolean>(false);
  const [paretoMetricFilter, setParetoMetricFilter] = useState<"ALL" | "L1" | "L2" | "L_inf">("ALL");
  const [axisX, setAxisX] = useState<number>(0);
  const [axisY, setAxisY] = useState<number>(1);
  const [axis3DX, setAxis3DX] = useState<number>(0);
  const [axis3DY, setAxis3DY] = useState<number>(1);
  const [axis3DZ, setAxis3DZ] = useState<number>(2);
  const [showAllVars, setShowAllVars] = useState<boolean>(false);
  const isDark = theme === "dark";

  const headers = solveResult?.payoff?.headers || model.objectives.map((o) => o.name);
  const nObjs = headers.length;
  const nVars = model.variables.length;

  // Reiniciar selección de ejes solo cuando cambia el número de objetivos o se carga un modelo/preset nuevo
  useEffect(() => {
    setAxisX(0);
    setAxisY(Math.min(1, Math.max(0, nObjs - 1)));
    setAxis3DX(0);
    setAxis3DY(Math.min(1, Math.max(0, nObjs - 1)));
    setAxis3DZ(Math.min(2, Math.max(0, nObjs - 1)));
    setShowAllVars(false);
    setParetoMetricFilter("ALL");
  }, [nObjs, modelKey]);

  const safeAxisX = axisX < nObjs ? axisX : 0;
  const safeAxisY = axisY < nObjs && axisY !== safeAxisX ? axisY : safeAxisX === 0 ? Math.min(1, nObjs - 1) : 0;

  // Garantizar 3 ejes distintos para el visualizador 3D
  const safe3DX = axis3DX < nObjs ? axis3DX : 0;
  const safe3DY =
    axis3DY < nObjs && axis3DY !== safe3DX
      ? axis3DY
      : [0, 1, 2].find((i) => i < nObjs && i !== safe3DX) ?? 0;
  const safe3DZ =
    axis3DZ < nObjs && axis3DZ !== safe3DX && axis3DZ !== safe3DY
      ? axis3DZ
      : [0, 1, 2, 3].find((i) => i < nObjs && i !== safe3DX && i !== safe3DY) ?? Math.min(2, nObjs - 1);

  const [stacked, setStacked] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 1150px)");
    const update = () => setStacked(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const sweep = solveResult?.weight_sensitivity;
  const sensitivityBase = useMemo(
    () => sweep ? sensitivityCurves(sweep, isDark) : [],
    [sweep, isDark],
  );

  const effectiveTab: ChartTab =
    (chartTab === "objectives3d" || chartTab === "radar") && nObjs < 3
      ? "objectives2d"
      : (chartTab === "sensitivity" && nObjs !== 2) || (chartTab === "decision2d" && nVars !== 2)
      ? "objectives2d"
      : chartTab;

  useEffect(() => {
    setPngError("");
  }, [effectiveTab, modelKey, solveResult]);

  const handleDownloadPng = async () => {
    if (!isCurrentResult || isExportingPng) return;
    setPngError("");
    setIsExportingPng(true);
    try {
      const container = document.querySelector("#grafico-resultados .js-plotly-plot") as HTMLElement | null;
      if (!container) throw new Error("No se encontró el gráfico activo.");
      const Plotly = await import("plotly.js-dist-min").then((m) => m.default);
      const dataUrl = await Plotly.toImage(container, { format: "png", width: 1400, height: 840, scale: 2 });
      const slug = (model.name || "grafico")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "") || "grafico";
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = `OptiCompromise_${slug}_${effectiveTab}.png`;
      link.click();
    } catch (err: unknown) {
      setPngError(err instanceof Error ? err.message : "No se pudo exportar la imagen PNG.");
    } finally {
      setIsExportingPng(false);
    }
  };

  const chartGuide: Record<ChartTab, [string, string]> = {
    objectives2d: ["Espacio de objetivos", "Ubica el ideal, la frontera aproximada y las soluciones compromiso en dos criterios."],
    objectives3d: ["Explorar tres criterios", "Gira la figura para comparar los compromisos entre los tres ejes."],
    radar: ["Perfil de logro", "Compara el porcentaje de logro por criterio. Cada eje representa un objetivo."],
    decision2d: ["Región de decisiones", "Ubica las cantidades elegidas y contrástalas con la región factible."],
    sensitivity: ["Efecto de los pesos", "Compara cuánto se aleja cada objetivo del ideal al variar la ponderación."],
  };

  const chart2D = useMemo(() => {
    if (!solveResult) return null;
    const { data2D, layout2D } = objectivePlot2D(
      model, solveResult, [safeAxisX, safeAxisY], isDark, { showPareto, showFeasibleObj, showIsodistance },
    );
    return { data: data2D, layout: { ...layout2D, uirevision: `objetivos-${modelKey}-${safeAxisX}-${safeAxisY}` } };
  }, [model, modelKey, solveResult, safeAxisX, safeAxisY, isDark, showPareto, showFeasibleObj, showIsodistance]);
  const chart3D = useMemo(() => {
    if (!solveResult || nObjs < 3) return null;
    const { data3D, layout3D } = objectivePlot3D(solveResult, [safe3DX, safe3DY, safe3DZ], isDark, showPareto);
    return { data: data3D, layout: { ...layout3D, uirevision: `3d-${modelKey}-${safe3DX}-${safe3DY}-${safe3DZ}` } };
  }, [solveResult, modelKey, nObjs, safe3DX, safe3DY, safe3DZ, isDark, showPareto]);
  const radar = useMemo(() => {
    if (!solveResult || nObjs < 3) return null;
    const { dataRadar, layoutRadar } = radarPlot(solveResult, isDark);
    return { data: dataRadar, layout: { ...layoutRadar, uirevision: `radar-${modelKey}` } };
  }, [solveResult, modelKey, nObjs, isDark]);
  const decision = useMemo(() => {
    if (!solveResult || nVars !== 2) return null;
    const { dataDec, layoutDec } = decisionPlot(model, solveResult, isDark);
    return { data: dataDec, layout: { ...layoutDec, uirevision: `decisiones-${modelKey}` } };
  }, [model, modelKey, solveResult, nVars, isDark]);
  const sensitivity = useMemo(() => {
    if (!solveResult || !sensitivityBase.length) return null;
    const selection = sensitivitySelection(solveResult, selectedWeight, isDark);
    return {
      data: [...sensitivityBase, ...selection.traces],
      layout: { ...sensitivityLayout(stacked, isDark), shapes: selection.shapes, uirevision: `sensibilidad-${modelKey}-${stacked}` },
    };
  }, [solveResult, selectedWeight, isDark, sensitivityBase, stacked, modelKey]);

  // Estado vacío o error inicial (si ya existe solveResult previo, mantenemos el contexto con banner arriba)
  const hasActiveError =
    solverStatus === "infeasible" || solverStatus === "unbounded" || solverStatus === "error";

  if (hasActiveError && !solveResult) {
    return (
      <main className="workspace-output min-w-0 flex items-start justify-center py-6">
        <div className="max-w-lg w-full rounded-sm border border-[#E11D48] bg-white dark:bg-slate-900 p-6 space-y-3 shadow-sm">
          <div className="flex items-center gap-3 text-[#E11D48]">
            <AlertOctagon className="w-7 h-7 shrink-0" />
            <div>
              <h2 className="text-base font-bold">
                {solverStatus === "infeasible"
                  ? "Modelo Infactible"
                  : solverStatus === "unbounded"
                  ? "Modelo No Acotado"
                  : "Error del Motor de Optimización"}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Revisa el detalle del motor y ajusta el modelo.
              </p>
            </div>
          </div>
          <div className="p-3 rounded-sm bg-rose-500/10 border border-rose-500/20 font-mono text-xs text-[#E11D48] dark:text-rose-300 break-words">
            {solverMessage}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Revisa las restricciones, sentidos (≤, ≥, =) o cotas de variables en Formular.
          </p>
        </div>
      </main>
    );
  }

  if (!solveResult) {
    return (
      <main className="workspace-output min-w-0 flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <Loader2 className="w-7 h-7 animate-spin text-[#E11D48]" />
          <span className="text-xs font-mono">Conectando con motor FastAPI (HiGHS / SLSQP)...</span>
        </div>
      </main>
    );
  }

  const solL1 = solveResult.solutions.L1;
  const solL2 = solveResult.solutions.L2;
  const solLinf = solveResult.solutions.L_inf;
  const degenerateObjs = solveResult.payoff.degenerate_objectives || [];

  return (
    <main className="workspace-output min-w-0 space-y-4">
      {hasActiveError && (
        <div className="rounded-sm border-2 border-[#E11D48] bg-rose-50 dark:bg-rose-950/50 px-4 py-3 flex items-start gap-3 text-xs text-rose-900 dark:text-rose-100">
          <AlertOctagon className="w-5 h-5 text-[#E11D48] shrink-0 mt-0.5" />
          <div className="space-y-1 min-w-0">
            <div className="font-bold">
              {solverStatus === "infeasible"
                ? "Edición actual infactible — mostrando último resultado válido debajo"
                : solverStatus === "unbounded"
                ? "Edición actual no acotada — mostrando último resultado válido debajo"
                : "Error pendiente en la edición actual — mostrando último resultado válido debajo"}
            </div>
            <div className="font-mono text-[11px] break-words text-[#E11D48] dark:text-rose-300">
              {solverMessage}
            </div>
          </div>
        </div>
      )}

      {degenerateObjs.length > 0 && (
        <div className="rounded-sm border border-amber-400 bg-amber-50 dark:bg-amber-950/30 px-3.5 py-2.5 text-[11px] text-amber-900 dark:text-amber-200">
          <b>Objetivos con rango observado nulo:</b>{" "}
          {degenerateObjs.map((idx) => headers[idx] || `Z${idx + 1}`).join(", ")}. Los valores observados se conservan. Consulta el tratamiento de cada criterio en Ver método.
        </div>
      )}

      {workspace === "results" && reportSlot && createPortal(
        <ResultDownloads model={model} result={solveResult} axes2d={[safeAxisX, safeAxisY]}
          axes3d={[safe3DX, safe3DY, safe3DZ]} disabled={!isCurrentResult} />,
        reportSlot,
      )}
      <div hidden={workspace !== "results"} aria-busy={solverStatus === "calculating"} className="space-y-4">
      {/* 1. GRÁFICO PRINCIPAL INTERACTIVO */}
      <section className="rounded-sm border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden" id="grafico-resultados" aria-labelledby="grafico-titulo">
        <div className="chart-intro px-4 py-3">
          <div className="flex flex-wrap justify-between items-start gap-3">
            <SectionHeading level="h3" id="grafico-titulo" title={chartGuide[effectiveTab][0]} cue={chartGuide[effectiveTab][1]} />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
          {/* Pestañas de vista gráfica */}
          <div className="chart-tabs flex flex-wrap items-center gap-1">
            <button
              type="button"
              onClick={() => setChartTab("objectives2d")}
              aria-pressed={effectiveTab === "objectives2d"}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-semibold transition-colors"
            >
              <Compass className="w-3.5 h-3.5" />
              <span>Objetivos 2D</span>
            </button>

            {nObjs === 2 && (
              <button type="button" aria-pressed={effectiveTab === "sensitivity"}
                onClick={() => setChartTab("sensitivity")}
                className="px-2.5 py-1 rounded-sm text-xs font-semibold">
                Sensibilidad de pesos
              </button>
            )}
            {nObjs >= 3 && (
              <>
                <button
                  type="button"
                  onClick={() => setChartTab("objectives3d")}
                  aria-pressed={effectiveTab === "objectives3d"}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-semibold transition-colors"
                >
                  <Box className="w-3.5 h-3.5" />
                  <span>Espacio 3D</span>
                </button>
                <button
                  type="button"
                  onClick={() => setChartTab("radar")}
                  aria-pressed={effectiveTab === "radar"}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-semibold transition-colors"
                >
                  <Target className="w-3.5 h-3.5" />
                  <span>Radar (% Logro)</span>
                </button>
              </>
            )}

            {nVars === 2 && (
              <button
                type="button"
                onClick={() => setChartTab("decision2d")}
                aria-pressed={effectiveTab === "decision2d"}
                title={`Región Factible (${model.variables[0].name} vs ${model.variables[1].name})`}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-semibold transition-colors"
              >
                <Grid className="w-3.5 h-3.5" />
                <span>Región Factible (2D)</span>
              </button>
            )}
          </div>

          {/* Controles del gráfico */}
          <div className="flex flex-wrap items-center gap-2.5 text-[11px]">
            <button
              type="button"
              disabled={!isCurrentResult || isExportingPng}
              onClick={() => void handleDownloadPng()}
              title={isCurrentResult ? "Descargar este gráfico como imagen PNG" : "Resuelve un modelo válido para descargar el gráfico"}
              className="inline-flex items-center gap-1 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 text-[11px] font-semibold text-slate-700 dark:text-slate-200 hover:border-[#E11D48] hover:text-[#E11D48] disabled:opacity-45 transition-colors"
            >
              <Download className="w-3 h-3" aria-hidden="true" />
              <span>{isExportingPng ? "Generando..." : "PNG"}</span>
            </button>
            {(effectiveTab === "objectives2d" || effectiveTab === "objectives3d") && (
              <>
                {effectiveTab === "objectives2d" && nVars === 2 && (
                  <label htmlFor="toggle-feasible-obj" className="inline-flex items-center gap-1.5 cursor-pointer select-none text-slate-600 dark:text-slate-300">
                    <input
                      id="toggle-feasible-obj"
                      name="toggle-feasible-obj"
                      type="checkbox"
                      checked={showFeasibleObj}
                      onChange={(e) => setShowFeasibleObj(e.target.checked)}
                      className="accent-[#E11D48] rounded-sm"
                    />
                    <span>Zona Factible</span>
                  </label>
                )}
                {effectiveTab === "objectives2d" && (
                  <label htmlFor="toggle-isodistance" className="inline-flex items-center gap-1.5 cursor-pointer select-none text-slate-600 dark:text-slate-300">
                    <input
                      id="toggle-isodistance"
                      name="toggle-isodistance"
                      type="checkbox"
                      checked={showIsodistance}
                      onChange={(e) => setShowIsodistance(e.target.checked)}
                      className="accent-[#E11D48] rounded-sm"
                    />
                    <span>Curvas Isodistancia</span>
                  </label>
                )}
                <label htmlFor="toggle-pareto" className="inline-flex items-center gap-1.5 cursor-pointer select-none text-slate-600 dark:text-slate-300">
                  <input
                    id="toggle-pareto"
                    name="toggle-pareto"
                    type="checkbox"
                    checked={showPareto}
                    onChange={(e) => setShowPareto(e.target.checked)}
                    className="accent-[#E11D48] rounded-sm"
                  />
                  <span>Frontera Pareto</span>
                </label>
              </>
            )}

            {effectiveTab === "objectives2d" && nObjs > 2 && (
              <div className="grid min-w-0 w-full gap-1 sm:flex sm:flex-wrap">
                <select
                  id="axis-x-select"
                  name="axis-x"
                  value={safeAxisX}
                  aria-label="Objetivo del eje X"
                  onChange={(e) => {
                    const next = parseInt(e.target.value, 10);
                    if (next === safeAxisY) setAxisY(safeAxisX);
                    setAxisX(next);
                  }}
                  className="min-w-0 max-w-full bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded px-1.5 py-0.5 text-[11px]"
                >
                  {headers.map((h, i) => (
                    <option key={i} value={i}>X: {h}</option>
                  ))}
                </select>
                <select
                  id="axis-y-select"
                  name="axis-y"
                  value={safeAxisY}
                  aria-label="Objetivo del eje Y"
                  onChange={(e) => {
                    const next = parseInt(e.target.value, 10);
                    if (next === safeAxisX) setAxisX(safeAxisY);
                    setAxisY(next);
                  }}
                  className="min-w-0 max-w-full bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded px-1.5 py-0.5 text-[11px]"
                >
                  {headers.map((h, i) => (
                    <option key={i} value={i}>Y: {h}</option>
                  ))}
                </select>
              </div>
            )}

            {effectiveTab === "objectives3d" && nObjs > 3 && (
              <div className="grid min-w-0 w-full gap-1 sm:flex sm:flex-wrap">
                <select
                  id="axis-3dx-select"
                  name="axis-3dx"
                  value={safe3DX}
                  aria-label="Objetivo del eje X 3D"
                  onChange={(e) => {
                    const next = parseInt(e.target.value, 10);
                    if (next === safe3DY) setAxis3DY(safe3DX);
                    else if (next === safe3DZ) setAxis3DZ(safe3DX);
                    setAxis3DX(next);
                  }}
                  className="min-w-0 max-w-full bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded px-1 py-0.5 text-[11px]"
                >
                  {headers.map((h, i) => <option key={i} value={i}>X: {h}</option>)}
                </select>
                <select
                  id="axis-3dy-select"
                  name="axis-3dy"
                  value={safe3DY}
                  aria-label="Objetivo del eje Y 3D"
                  onChange={(e) => {
                    const next = parseInt(e.target.value, 10);
                    if (next === safe3DX) setAxis3DX(safe3DY);
                    else if (next === safe3DZ) setAxis3DZ(safe3DY);
                    setAxis3DY(next);
                  }}
                  className="min-w-0 max-w-full bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded px-1 py-0.5 text-[11px]"
                >
                  {headers.map((h, i) => <option key={i} value={i}>Y: {h}</option>)}
                </select>
                <select
                  id="axis-3dz-select"
                  name="axis-3dz"
                  value={safe3DZ}
                  aria-label="Objetivo del eje Z 3D"
                  onChange={(e) => {
                    const next = parseInt(e.target.value, 10);
                    if (next === safe3DX) setAxis3DX(safe3DZ);
                    else if (next === safe3DY) setAxis3DY(safe3DZ);
                    setAxis3DZ(next);
                  }}
                  className="min-w-0 max-w-full bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded px-1 py-0.5 text-[11px]"
                >
                  {headers.map((h, i) => <option key={i} value={i}>Z: {h}</option>)}
                </select>
              </div>
            )}

          </div>
        </div>

        {(effectiveTab === "decision2d" || (effectiveTab === "objectives2d" && showFeasibleObj)) &&
          solveResult.payoff.decision_ranges_2d?.some(([lo, hi]) => lo === null || hi === null) && (
          <p className="px-4 pt-2 text-xs text-slate-600 dark:text-slate-300">La región se muestra recortada en los ejes sin cota finita confirmada.</p>
        )}
        {pngError && (
          <p role="alert" className="px-4 pt-2 text-xs text-rose-800 dark:text-rose-300">{pngError}</p>
        )}
        {workspace === "results" && <div className="plot-frame p-2">
          <p className="sr-only">Consulta los valores accesibles en la tabla de comparación de soluciones.</p>
          {effectiveTab === "sensitivity" && (sweep && sensitivity ? (() => {
            const partial = [...(sweep.l1 ?? []), ...(sweep.l2 ?? []), ...(sweep.l_inf ?? [])].some(point => point?.status !== "optimal");
            return (
              <div className="min-w-0">
                <p className="px-3 py-2 text-xs leading-relaxed text-slate-700 dark:text-slate-200">
                  Peso de {sweep.objective_name}. La línea punteada indica w₁ seleccionado. Los marcadores grandes muestran el último cálculo resuelto.
                  Los tramos conectan muestras. En L₁ puede haber saltos y óptimos alternativos.
                  {partial && " El barrido incluye resultados factibles sin certificado o muestras sin solución."}
                </p>
                <Plot data={sensitivity.data} layout={sensitivity.layout}
                  config={sensitivityConfig} useResizeHandler
                  style={{ width: "100%" }} />
              </div>
            );
          })() : <p role="status" className="p-5 text-sm">El barrido de sensibilidad no está disponible para este cálculo.</p>)}
          {effectiveTab === "objectives2d" && chart2D && (
            <Plot
              data={chart2D.data}
              layout={chart2D.layout}
              config={plotConfig}
              useResizeHandler
              style={{ width: "100%", height: "clamp(320px, 46vw, 470px)" }}
            />
          )}
          {effectiveTab === "objectives3d" && chart3D && (
            <Plot
              data={chart3D.data}
              layout={chart3D.layout}
              config={plotConfig}
              useResizeHandler
              style={{ width: "100%", height: "clamp(340px, 46vw, 470px)" }}
            />
          )}
          {effectiveTab === "radar" && radar && (
            <Plot
              data={radar.data}
              layout={radar.layout}
              config={plotConfig}
              useResizeHandler
              style={{ width: "100%", height: "clamp(340px, 46vw, 470px)" }}
            />
          )}
          {effectiveTab === "decision2d" && decision && (
            <Plot
              data={decision.data}
              layout={decision.layout}
              config={plotConfig}
              useResizeHandler
              style={{ width: "100%", height: "clamp(320px, 46vw, 470px)" }}
            />
          )}
        </div>}

        {effectiveTab === "objectives2d" && (
          <details className="method-disclosure px-4 text-xs text-slate-700 dark:text-slate-200">
            <summary>Guía de curvas de isodistancia</summary>
            <p>Activa <strong>Curvas Isodistancia</strong> para comparar sus niveles con las muestras de Pareto. Con dos pesos positivos y objetivos que varían, las formas visibles son:</p>
            <dl className="grid gap-2 pb-3 sm:grid-cols-3">
              <div><dt className="font-bold text-blue-700 dark:text-blue-300">L₁ · Segmento recto</dt>
                <dd>Los puntos del segmento comparten la suma de brechas ponderadas. Si coincide con una arista de la frontera, puede haber empate.</dd></div>
              <div><dt className="font-bold">L₂ · Arco de elipse</dt>
                <dd>El arco tiene centro en el ideal. Puede tocar de forma tangente una frontera lisa.</dd></div>
              <div><dt className="font-bold text-rose-700 dark:text-rose-300">L∞ · Esquina rectangular</dt>
                <dd>Sus lados mantienen constante la mayor brecha ponderada.</dd></div>
            </dl>
            <p>Si solo un peso es positivo, la distancia en la vista depende de ese eje. Con tres o más objetivos, las curvas usan los dos ejes elegidos.</p>
          </details>
        )}

        {/* Explorador de Puntos de la Frontera Eficiente (Pesos × Métricas) */}
        {effectiveTab !== "sensitivity" && (() => {
          const allPareto = validParetoPoints(solveResult);
          const countL1 = allPareto.filter((p) => p.metric === "L1").length;
          const countL2 = allPareto.filter((p) => p.metric === "L2").length;
          const countLinf = allPareto.filter((p) => p.metric === "L_inf").length;
          const filteredPts =
            paretoMetricFilter === "ALL"
              ? allPareto
              : allPareto.filter((p) => p.metric === paretoMetricFilter);

          return (
            <div className="border-t border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50">
              <button
                type="button"
                onClick={() => setParetoExplorerOpen((prev) => !prev)}
                className="w-full px-4 py-2 flex items-center justify-between gap-3 text-left hover:bg-slate-100/70 dark:hover:bg-slate-800/60 transition-colors"
              >
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  <span className="font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">
                    Aproximación de Pareto ({allPareto.length} puntos)
                  </span>
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded-sm bg-[#2563EB]/10 text-[#2563EB] dark:text-blue-400 font-mono font-semibold">
                    L₁: {countL1}
                  </span>
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded-sm bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono font-semibold">
                    L₂: {countL2}
                  </span>
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded-sm bg-[#E11D48]/10 text-[#E11D48] font-mono font-semibold">
                    L∞: {countLinf}
                  </span>
                </div>
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-500 dark:text-slate-400 shrink-0">
                  <span>{paretoExplorerOpen ? "Ocultar detalle" : "Ver pesos y métricas"}</span>
                  {paretoExplorerOpen ? (
                    <ChevronUp className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronDown className="w-3.5 h-3.5" />
                  )}
                </span>
              </button>

              {paretoExplorerOpen && (
                <div className="px-4 pb-3 pt-1 space-y-2 border-t border-slate-200/70 dark:border-slate-800">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    <p className="text-slate-500 dark:text-slate-400">
                      Puntos no dominados entre las soluciones del barrido de pesos. La línea conecta muestras como guía visual. El estado del solver corresponde a la métrica de cada punto.
                    </p>
                    <div className="flex items-center gap-1">
                      {(
                        [
                          { id: "ALL", label: `Todos (${allPareto.length})` },
                          { id: "L1", label: `L₁ (${countL1})` },
                          { id: "L2", label: `L₂ (${countL2})` },
                          { id: "L_inf", label: `L∞ (${countLinf})` },
                        ] as const
                      ).map((tab) => (
                        <button
                          key={tab.id}
                          type="button"
                          onClick={() => setParetoMetricFilter(tab.id)}
                          className={`px-2 py-0.5 rounded-sm font-mono font-semibold border transition-colors ${
                            paretoMetricFilter === tab.id
                              ? "bg-[#E11D48] text-white border-[#E11D48]"
                              : "bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-300 dark:border-slate-700 hover:border-[#E11D48]"
                          }`}
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="max-h-52 overflow-y-auto border border-slate-200 dark:border-slate-800 rounded-sm bg-white dark:bg-slate-900">
                    <table className="w-full text-[11px] font-mono">
                      <thead className="sticky top-0 bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700 text-right">
                        <tr>
                          <th className="py-1.5 px-2 text-left w-10">#</th>
                          <th className="py-1.5 px-2 text-left">Métrica</th>
                          <th className="py-1.5 px-2 text-left">Pesos (wᵢ)</th>
                          <th className="py-1.5 px-2 text-left">Estado</th>
                          {headers.map((h, i) => (
                            <th key={i} className="py-1.5 px-2 max-w-[120px] truncate" title={h}>
                              Z{i + 1}
                            </th>
                          ))}
                          {onApplyParetoWeights && <th className="py-1.5 px-2 text-center">Acción</th>}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
                        {filteredPts.map((pt, idx) => {
                          const badgeClass =
                            pt.metric === "L1"
                              ? "bg-[#2563EB]/10 text-[#2563EB] dark:text-blue-400"
                              : pt.metric === "L_inf"
                              ? "bg-[#E11D48]/10 text-[#E11D48]"
                              : "bg-slate-200/80 dark:bg-slate-800 text-slate-700 dark:text-slate-300";
                          const varsSummary = Object.entries(pt.variables)
                            .map(([k, v]) => `${k}=${fmtNum(v, 3)}`)
                            .join(" · ");
                          return (
                            <tr
                              key={`${pt.metric}-${idx}`}
                              title={varsSummary || undefined}
                              className="hover:bg-slate-50 dark:hover:bg-slate-800/40"
                            >
                              <td className="py-1 px-2 text-left text-slate-400">{idx + 1}</td>
                              <td className="py-1 px-2 text-left">
                                <span className={`inline-block px-1.5 py-0.5 rounded-sm font-bold ${badgeClass}`}>
                                  {pt.metric === "L_inf" ? "L∞" : pt.metric}
                                </span>
                              </td>
                              <td className="py-1 px-2 text-left text-slate-600 dark:text-slate-300">
                                [{pt.weights.map((w) => `${(w * 100).toFixed(2)}%`).join(", ")}]
                              </td>
                              <td className="py-1 px-2 text-left">{pt.status === "feasible_suboptimal" ? "Factible sin certificado" : pt.status === "optimal" ? "Óptimo de la métrica" : "—"}</td>
                              {pt.objectives.map((val, k) => (
                                <td key={k} className="py-1 px-2 text-right font-semibold text-slate-800 dark:text-slate-100">
                                  {fmtNum(val)}
                                </td>
                              ))}
                              {onApplyParetoWeights && (
                                <td className="py-1 px-2 text-center">
                                  <button
                                    type="button"
                                    onClick={() => onApplyParetoWeights(pt.weights)}
                                    className="px-1.5 py-0.5 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-[10px] font-sans font-semibold text-slate-700 dark:text-slate-200 hover:border-[#E11D48] hover:text-[#E11D48]"
                                  >
                                    Usar pesos
                                  </button>
                                </td>
                              )}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          );
        })()}
      </section>

      {solverStatus === "partial" && (
        <div className="rounded-sm border border-amber-400 bg-amber-50 dark:bg-amber-950/30 px-3.5 py-2.5 text-[11px] text-amber-900 dark:text-amber-200">
          <b>{solverMessage}</b>
          <ul className="mt-1">
            {Object.values(solveResult.solutions).filter((s) => s.status !== "optimal").map((s) => (
              <li key={s.metric}>{s.metric.replace("L_inf", "L∞")}: {s.status === "feasible_suboptimal" ? "Solución factible sin certificado de optimalidad." : "No hay una solución disponible."}</li>
            ))}
          </ul>
        </div>
      )}
      {/* 2. TABLA UNIFICADA: SOLUCIONES COMPROMISO (VALORES, % LOGRO Y DISTANCIA D_p) */}
      <section className="rounded-sm border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3.5 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <SectionHeading title="Comparación de soluciones"
            cue="Compara el valor y el logro de cada objetivo en las tres soluciones." />
        </div>
        <div className="overflow-x-auto cockpit-scroll" role="region" aria-label="Datos de las soluciones" tabIndex={0}>
          <table className="data-table w-full border-collapse">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400">
                <th className="text-left py-2 pr-3 font-semibold">Criterio / Métrica</th>
                <th className="text-center py-2 px-2 font-semibold">Peso (wᵢ)</th>
                <th className="text-right py-2 px-3 font-bold text-[#2563EB] dark:text-blue-400">L₁ (Manhattan)</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 dark:text-slate-200">L₂ (Euclidiana)</th>
                <th className="text-right py-2 pl-3 font-bold text-[#E11D48]">L∞ (Minimax)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 font-mono">
              <tr className="bg-slate-50 dark:bg-slate-800/40">
                <td className="py-2 pr-3 font-sans font-bold text-slate-800 dark:text-slate-100">
                  Distancia Agregada Dₚ al Ideal
                </td>
                <td className="py-2 px-2 text-center text-[11px] text-slate-500">
                  Σw = {(solveResult.weights.reduce((a, b) => a + b, 0)).toFixed(2)}
                </td>
                <td className="py-2 px-3 text-right text-[#2563EB] dark:text-blue-400 font-bold text-sm">
                  {solL1?.objectives?.length ? fmtNum(solL1.aggregate_distance, 4) : "—"}
                </td>
                <td className="py-2 px-3 text-right text-slate-900 dark:text-slate-100 font-bold text-sm">
                  {solL2?.objectives?.length ? fmtNum(solL2.aggregate_distance, 4) : "—"}
                </td>
                <td className="py-2 pl-3 text-right text-[#E11D48] font-bold text-sm">
                  {solLinf?.objectives?.length ? fmtNum(solLinf.aggregate_distance, 4) : "—"}
                </td>
              </tr>

              {headers.map((h, i) => {
                const wPct = fmtNum((solveResult.weights[i] ?? 0) * 100, 2);
                const cols = [
                  { sol: solL1, bar: "bg-[#2563EB]", text: "text-[#2563EB] dark:text-blue-400" },
                  { sol: solL2, bar: "bg-[#334155] dark:bg-slate-400", text: "text-slate-800 dark:text-slate-200" },
                  { sol: solLinf, bar: "bg-[#E11D48]", text: "text-[#E11D48]" },
                ];
                return (
                  <tr key={`obj-${i}`} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/30">
                    <td className="py-2.5 pr-3 font-sans">
                      <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                        Z{i + 1}: {h}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">
                        {model.objectives[i]?.sense === "maximize" ? "▲ Maximizar" : "▼ Minimizar"}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 text-center">
                      <span className="px-1.5 py-0.5 rounded-sm bg-rose-50 dark:bg-rose-950/40 text-[#E11D48] dark:text-rose-300 border border-rose-200 dark:border-rose-800 text-[10px] font-bold">
                        {wPct}%
                      </span>
                    </td>
                    {cols.map((col, cIdx) => {
                      const pct = col.sol?.achievement_pct?.[i];
                      return (
                        <td key={cIdx} className={`py-2.5 ${cIdx === 2 ? "pl-3" : "px-3"} text-right align-top`}>
                          <div className="font-bold text-slate-900 dark:text-slate-100">
                            {fmtNum(col.sol?.objectives?.[i], 2)}
                          </div>
                          {pct !== undefined && Number.isFinite(pct) && <div className="mt-1 flex items-center justify-end gap-2">
                            <div className="w-16 sm:w-20 h-1.5 bg-slate-200 dark:bg-slate-800 overflow-hidden">
                              <div className={`h-full ${col.bar} transition-all duration-300`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
                            </div>
                            <span className={`text-[10px] font-bold tabular-nums min-w-[4rem] whitespace-nowrap text-right ${col.text}`}>
                              {fmtAchievement(pct)}
                            </span>
                          </div>}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* 3. SECCIÓN EXPLÍCITA: DECISIONES ÓPTIMAS POR VARIABLE (VECTOR x*) */}
      <section className="rounded-sm border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3.5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionHeading title="Valores de las variables"
            cue="Consulta las cantidades que tendrías que aplicar en cada solución." />
          {model.variables.length > 6 && (
            <button
              type="button"
              onClick={() => setShowAllVars((s) => !s)}
              className="text-[11px] font-bold text-[#E11D48] hover:underline cursor-pointer"
            >
              {showAllVars ? "Mostrar resumen (6)" : `Ver todas las ${model.variables.length} variables`}
            </button>
          )}
        </div>

        <div className="overflow-x-auto cockpit-scroll" role="region" aria-label="Variables por métrica" tabIndex={0}>
          <table className="data-table w-full border-collapse">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400">
                <th className="text-left py-2 pr-3 font-semibold">Variable</th>
                <th className="text-center py-2 px-2 font-semibold">Tipo / Dominio</th>
                <th className="text-right py-2 px-3 font-bold text-[#2563EB] dark:text-blue-400">L₁ (x*)</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 dark:text-slate-200">L₂ (x*)</th>
                <th className="text-right py-2 pl-3 font-bold text-[#E11D48]">L∞ (x*)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 font-mono">
              {(showAllVars ? model.variables : model.variables.slice(0, 6)).map((v) => {
                const typeLabel =
                  v.var_type === "binary" ? "Binaria {0,1}" : v.var_type === "integer" ? "Entera ℤ" : "Continua ℝ";
                const boundsLabel =
                  v.var_type === "binary"
                    ? "[0, 1]"
                    : `[${v.lower_bound ?? "-∞"}, ${v.upper_bound ?? "+∞"}]`;
                return (
                  <tr key={`var-sec-${v.name}`} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/30">
                    <td className="py-1.5 pr-3 font-semibold text-slate-800 dark:text-slate-100">
                      {v.name}
                    </td>
                    <td className="py-1.5 px-2 text-center font-sans text-[10px] text-slate-500 dark:text-slate-400">
                      <span className="px-1.5 py-0.5 rounded-sm bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 font-medium mr-1">
                        {typeLabel}
                      </span>
                      <span className="font-mono">{boundsLabel}</span>
                    </td>
                    <td className="py-1.5 px-3 text-right font-bold text-[#2563EB] dark:text-blue-400">
                      {fmtNum(solL1?.variables?.[v.name], 3)}
                    </td>
                    <td className="py-1.5 px-3 text-right font-bold text-slate-900 dark:text-slate-100">
                      {fmtNum(solL2?.variables?.[v.name], 3)}
                    </td>
                    <td className="py-1.5 pl-3 text-right font-bold text-[#E11D48]">
                      {fmtNum(solLinf?.variables?.[v.name], 3)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      </div>
      {workspace === "method" && <MethodGuide model={model} result={solveResult} />}
    </main>
  );
}
