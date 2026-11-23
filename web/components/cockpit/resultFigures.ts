import { ModelDefinition, ParetoPoint, SEMANTIC_COLORS, SolveResponse } from "./types";
import {
  fmtNum,
  escapeMarkup,
  computeFeasiblePolygon2D,
  computeFeasibleObjectivesPolygon2D,
  computeDiscreteFeasiblePoints2D,
  computeIsodistanceTraces2D,
} from "./mathUtils";

type PlotTrace = Record<string, unknown>;
type ObjectiveLayers = { showPareto: boolean; showFeasibleObj: boolean; showIsodistance: boolean };

function palette(isDark: boolean) {
  const paperBg = isDark ? "#111524" : "#FFFFFF";
  const plotBg = isDark ? "#1E293B" : "#F8FAFC";
  const gridColor = isDark ? "#334155" : "#E2E8F0";
  const textColor = isDark ? "#E2E8F0" : "#0F172A";
  const l2Color = isDark ? "#CBD5E1" : SEMANTIC_COLORS.L2;
  return { paperBg, plotBg, gridColor, textColor, l2Color };
}

function hasCoordinates<Key extends string | number>(
  values: Partial<Record<Key, number>> | undefined,
  keys: readonly Key[],
): values is Record<Key, number> {
  return Boolean(values && keys.every(key => Number.isFinite(values[key])));
}

export function validParetoPoints(result: SolveResponse): ParetoPoint[] {
  const count = result.payoff.headers.length;
  const axes = result.payoff.headers.map((_, i) => i);
  return (result.pareto_points ?? []).filter(point =>
    point?.objectives?.length === count && hasCoordinates(point.objectives, axes)
    && point.weights?.length === count && hasCoordinates(point.weights, axes)
    && ["L1", "L2", "L_inf"].includes(point.metric));
}

function constantAxis(payoff: SolveResponse["payoff"], index: number): { range?: [number, number] } {
  if (payoff.normalization_sources?.[index] !== "constant") return {};
  const center = payoff.ideal_point?.[index];
  const margin = Math.max(1, Math.abs(center)) * 1e-4;
  const range: [number, number] = [center - margin, center + margin];
  return range.every(Number.isFinite) ? { range } : {};
}

export function objectivePlot2D(model: ModelDefinition, solveResult: SolveResponse, axes: [number, number], isDark: boolean, { showPareto, showFeasibleObj, showIsodistance }: ObjectiveLayers) {
  const { paperBg, plotBg, gridColor, textColor, l2Color } = palette(isDark);
  const headers = solveResult.payoff.headers.map(escapeMarkup);
  const nObjs = headers.length;
  const [safeAxisX, safeAxisY] = axes;
  const nVars = model.variables.length;
  const { payoff, solutions } = solveResult;
  const ideal = payoff.ideal_point ?? [];
  const nadir = payoff.anti_ideal_point ?? [];
  const isPure2D = nObjs === 2;
  const isMixedInt = model.variables.some((v) => v.var_type !== "continuous");

  const senseY2D = model.objectives[safeAxisY]?.sense ?? "maximize";
  const sortedPareto = validParetoPoints(solveResult).sort((a, b) => {
    const dx = a.objectives[safeAxisX] - b.objectives[safeAxisX];
    if (dx !== 0) return dx;
    return senseY2D === "maximize"
      ? b.objectives[safeAxisY] - a.objectives[safeAxisY]
      : a.objectives[safeAxisY] - b.objectives[safeAxisY];
  });

  const traces: PlotTrace[] = [];

  // 1. Zona Factible proyectada al Espacio de Objetivos (cuando nVars === 2)
  if (showFeasibleObj && nVars === 2) {
    const objPoly = computeFeasibleObjectivesPolygon2D(model, safeAxisX, safeAxisY, payoff);
    if (objPoly?.x.every(Number.isFinite) && objPoly.y.every(Number.isFinite)) {
      traces.push({
        x: objPoly.x,
        y: objPoly.y,
        mode: "lines",
        type: "scatter",
        fill: "toself",
        fillcolor: isDark ? "rgba(148, 163, 184, 0.14)" : "rgba(148, 163, 184, 0.20)",
        line: {
          color: isDark ? "#64748B" : "#94A3B8",
          width: 1.4,
          dash: isMixedInt ? "dot" : "solid",
        },
        name: isMixedInt ? "Relajación continua" : "Zona factible visible",
        hoverinfo: "name",
      });
    }
  }

  // 2. Caja de referencia Ideal–Nadir (líneas guía)
  const ix = ideal[safeAxisX];
  const iy = ideal[safeAxisY];
  const nx = nadir[safeAxisX];
  const ny = nadir[safeAxisY];
  if (
    Number.isFinite(ix) &&
    Number.isFinite(iy) &&
    Number.isFinite(nx) &&
    Number.isFinite(ny)
  ) {
    traces.push({
      x: [ix, nx, nx, ix, ix],
      y: [iy, iy, ny, ny, iy],
      mode: "lines",
      type: "scatter",
      name: "Caja de referencias de pagos",
      showlegend: false,
      line: { color: isDark ? "#475569" : "#CBD5E1", width: 1.2, dash: "dot" },
      hoverinfo: "name",
    });
  }

  // 3. Frontera Eficiente de Pareto (curva destacada + puntos clasificados por pesos y métricas)
  if (showPareto && sortedPareto.length > 0) {
    const senseX = model.objectives[safeAxisX]?.sense ?? "maximize";
    const senseY = model.objectives[safeAxisY]?.sense ?? "maximize";
    const spanX = payoff.normalization_ranges?.[safeAxisX] || Math.abs(ix - nx) || 1;
    const spanY = payoff.normalization_ranges?.[safeAxisY] || Math.abs(iy - ny) || 1;
    const better = (a: number, b: number, sense: string) =>
      sense === "maximize" ? a >= b - 1e-6 : a <= b + 1e-6;
    const strictlyBetter = (a: number, b: number, sense: string) =>
      sense === "maximize" ? a > b + 1e-6 : a < b - 1e-6;

    // En 3D+ se filtra también por dominancia entre las muestras proyectadas.
    const curveSource = isPure2D
      ? sortedPareto
      : sortedPareto.filter((p) => {
          const px = p.objectives[safeAxisX];
          const py = p.objectives[safeAxisY];
          return !sortedPareto.some((o) => {
            const ox = o.objectives[safeAxisX];
            const oy = o.objectives[safeAxisY];
            return (
              better(ox / spanX, px / spanX, senseX) &&
              better(oy / spanY, py / spanY, senseY) &&
              (strictlyBetter(ox / spanX, px / spanX, senseX) || strictlyBetter(oy / spanY, py / spanY, senseY))
            );
          });
        });

    const curvePts: ParetoPoint[] = [];
    curveSource.forEach((p) => {
      const last = curvePts[curvePts.length - 1];
      if (
        !last ||
        Math.abs(p.objectives[safeAxisX] - last.objectives[safeAxisX]) > 1e-4 * spanX ||
        Math.abs(p.objectives[safeAxisY] - last.objectives[safeAxisY]) > 1e-4 * spanY
      ) {
        curvePts.push(p);
      }
    });

    if (curvePts.length >= 2 && !isMixedInt) {
      traces.push({
        x: curvePts.map((p) => p.objectives[safeAxisX]),
        y: curvePts.map((p) => p.objectives[safeAxisY]),
        mode: "lines",
        type: "scatter",
        name: isPure2D ? "Unión de muestras Pareto" : "Unión de muestras proyectadas",
        line: {
          color: "#E11D48",
          width: isPure2D ? 3.5 : 2.2,
          dash: isPure2D ? "solid" : "dash",
        },
        hoverinfo: "name",
      });
    }

    const paretoMetricGroups = [
      { key: "L1", name: "Pareto L₁", color: SEMANTIC_COLORS.L1, symbol: "triangle-up" },
      { key: "L2", name: "Pareto L₂", color: isDark ? "#94A3B8" : "#64748B", symbol: "circle" },
      { key: "L_inf", name: "Pareto L∞", color: "#E11D48", symbol: "diamond" },
    ];

    paretoMetricGroups.forEach((grp) => {
      const pts = sortedPareto.filter((p) => p.metric === grp.key);
      if (pts.length === 0) return;
      traces.push({
        x: pts.map((p) => p.objectives[safeAxisX]),
        y: pts.map((p) => p.objectives[safeAxisY]),
        mode: "markers",
        type: "scatter",
        name: isMixedInt && isPure2D ? `${grp.name} (Discreto)` : grp.name,
        marker: {
          size: isMixedInt ? 7.5 : 6,
          symbol: grp.symbol,
          color: grp.color,
          line: { width: 1, color: "#FFFFFF" },
          opacity: isMixedInt ? 0.88 : 0.65,
        },
        hoverinfo: "text",
        hovertext: pts.map((p) => {
          const wStr = p.weights.map((w, idx) => `w${idx + 1}=${(w * 100).toFixed(2)}%`).join(", ");
          return `<b>Muestra Pareto (${grp.key === "L_inf" ? "L∞" : grp.key})</b><br>Pesos: ${wStr}<br>${headers[safeAxisX]}: ${fmtNum(p.objectives[safeAxisX])}<br>${headers[safeAxisY]}: ${fmtNum(p.objectives[safeAxisY])}`;
        }),
      });
    });
  }

  // Curvas de Isodistancia
  if (showIsodistance) {
    const isoTraces = computeIsodistanceTraces2D(
      model,
      payoff,
      solveResult.weights,
      solutions,
      safeAxisX,
      safeAxisY,
      isDark
    );
    isoTraces.filter(iso => iso.x.every(Number.isFinite) && iso.y.every(Number.isFinite)).forEach((iso) => {
      traces.push({
        x: iso.x,
        y: iso.y,
        mode: "lines",
        type: "scatter",
        name: nObjs === 2 ? iso.name : `${iso.name} · dos ejes`,
        line: { color: iso.color, width: 1.8, dash: iso.dash },
        hoverinfo: "name",
      });
    });
  }

  // Ideal
  if (hasCoordinates(ideal, axes)) traces.push({
    x: [ideal[safeAxisX]],
    y: [ideal[safeAxisY]],
    mode: "markers+text",
    type: "scatter",
    name: "Ideal (Z*)",
    text: ["★ Ideal"],
    textposition: "top center",
    cliponaxis: false,
    textfont: { color: SEMANTIC_COLORS.ideal, size: 11 },
    marker: {
      symbol: "star",
      size: 16,
      color: SEMANTIC_COLORS.ideal,
      line: { color: "#FFFFFF", width: 1 },
    },
  });

  // Nadir
  if (hasCoordinates(nadir, axes)) traces.push({
    x: [nadir[safeAxisX]],
    y: [nadir[safeAxisY]],
    mode: "markers+text",
    type: "scatter",
    name: "Nadir aproximado",
    text: ["✕ Nadir aprox."],
    textposition: "bottom center",
    cliponaxis: false,
    textfont: { color: SEMANTIC_COLORS.nadir, size: 11 },
    marker: { symbol: "x", size: 12, color: SEMANTIC_COLORS.nadir, line: { width: 2.5 } },
  });

  // L1, L2, L_inf (agrupar etiquetas si coinciden en el mismo punto para evitar solapamientos)
  const metricDefs = [
    { key: "L1", label: "L₁", name: "L₁ (Compensatoria)", color: SEMANTIC_COLORS.L1, symbol: "square", pos: "top right", size: 13 },
    { key: "L2", label: "L₂", name: "L₂ (Euclidiana)", color: l2Color, symbol: "circle", pos: "bottom right", size: 12 },
    { key: "L_inf", label: "L∞", name: "L∞ (Minimax)", color: SEMANTIC_COLORS.L_inf, symbol: "diamond", pos: "top left", size: 13 },
  ];
  const coordSpanX = payoff.normalization_ranges?.[safeAxisX] || Math.abs((ideal[safeAxisX] ?? 0) - (nadir[safeAxisX] ?? 0)) || 1;
  const coordSpanY = payoff.normalization_ranges?.[safeAxisY] || Math.abs((ideal[safeAxisY] ?? 0) - (nadir[safeAxisY] ?? 0)) || 1;

  metricDefs.forEach((m, idxM) => {
    const sol = solutions[m.key];
    if (!sol || !hasCoordinates(sol.objectives, axes)) return;
    const sx = sol.objectives[safeAxisX];
    const sy = sol.objectives[safeAxisY];
    const dupEarlier = metricDefs.slice(0, idxM).some((prev) => {
      const ps = solutions[prev.key];
      return (
        ps?.objectives &&
        Math.abs(ps.objectives[safeAxisX] - sx) < 1e-3 * coordSpanX &&
        Math.abs(ps.objectives[safeAxisY] - sy) < 1e-3 * coordSpanY
      );
    });
    const coLocated = metricDefs
      .filter((other) => {
        const os = solutions[other.key];
        return (
          os?.objectives &&
          Math.abs(os.objectives[safeAxisX] - sx) < 1e-3 * coordSpanX &&
          Math.abs(os.objectives[safeAxisY] - sy) < 1e-3 * coordSpanY
        );
      })
      .map((o) => o.label);

    traces.push({
      x: [sx],
      y: [sy],
      mode: dupEarlier ? "markers" : "markers+text",
      type: "scatter",
      name: m.name,
      text: dupEarlier ? undefined : [coLocated.join(" = ")],
      textposition: m.pos,
      cliponaxis: false,
      textfont: { color: m.color, size: 12 },
      marker: {
        symbol: m.symbol,
        size: m.size,
        color: m.color,
        line: { color: "#FFFFFF", width: 1.5 },
      },
      hoverinfo: "text",
      hovertext: `<b>${m.name}</b><br>${headers[safeAxisX]}: ${fmtNum(sx)}<br>${headers[safeAxisY]}: ${fmtNum(sy)}<br>D_p: ${fmtNum(sol.aggregate_distance, 4)}`,
    });
  });

  return {
    data2D: traces,
    layout2D: {
      autosize: true,
      paper_bgcolor: paperBg,
      plot_bgcolor: plotBg,
      font: { color: textColor, size: 11 },
      xaxis: { ...constantAxis(payoff, safeAxisX), title: { text: headers[safeAxisX] }, gridcolor: gridColor, zerolinecolor: gridColor, automargin: true },
      yaxis: { ...constantAxis(payoff, safeAxisY), title: { text: headers[safeAxisY] }, gridcolor: gridColor, zerolinecolor: gridColor, automargin: true },
      legend: { orientation: "h", y: -0.25, font: { size: 10 } },
      margin: { l: 64, r: 48, t: 22, b: 84 },
    },
  };
}

export function objectivePlot3D(solveResult: SolveResponse, axes: [number, number, number], isDark: boolean, showPareto: boolean) {
  const { paperBg, plotBg, gridColor, textColor, l2Color } = palette(isDark);
  const headers = solveResult.payoff.headers.map(escapeMarkup);
  const [safe3DX, safe3DY, safe3DZ] = axes;
  const { payoff, solutions } = solveResult;
  const ideal = payoff.ideal_point ?? [];
  const nadir = payoff.anti_ideal_point ?? [];

  const traces: PlotTrace[] = [];
  const paretoPoints = showPareto ? validParetoPoints(solveResult) : [];
  if (paretoPoints.length > 0) {
    const paretoMetricGroups3D = [
      { key: "L1", name: "Pareto L₁", color: SEMANTIC_COLORS.L1, symbol: "diamond" },
      { key: "L2", name: "Pareto L₂", color: isDark ? "#94A3B8" : "#64748B", symbol: "circle" },
      { key: "L_inf", name: "Pareto L∞", color: "#E11D48", symbol: "cross" },
    ];
    paretoMetricGroups3D.forEach((grp) => {
      const pts = paretoPoints.filter((p) => p.metric === grp.key);
      if (pts.length === 0) return;
      traces.push({
        x: pts.map((p) => p.objectives[safe3DX]),
        y: pts.map((p) => p.objectives[safe3DY]),
        z: pts.map((p) => p.objectives[safe3DZ]),
        mode: "markers",
        type: "scatter3d",
        name: grp.name,
        marker: { size: 3.5, symbol: grp.symbol, color: grp.color, opacity: 0.35 },
        hoverinfo: "text",
        hovertext: pts.map((p) => {
          const wStr = p.weights.map((w, idx) => `w${idx + 1}=${(w * 100).toFixed(2)}%`).join(", ");
          return `<b>Pareto (${grp.key === "L_inf" ? "L∞" : grp.key})</b><br>Pesos: ${wStr}<br>${headers[safe3DX]}: ${fmtNum(p.objectives[safe3DX])}<br>${headers[safe3DY]}: ${fmtNum(p.objectives[safe3DY])}<br>${headers[safe3DZ]}: ${fmtNum(p.objectives[safe3DZ])}`;
        }),
      });
    });
  }

  if (hasCoordinates(ideal, axes)) traces.push({
    x: [ideal[safe3DX]],
    y: [ideal[safe3DY]],
    z: [ideal[safe3DZ]],
    mode: "markers+text",
    type: "scatter3d",
    name: "Ideal (Z*)",
    text: ["★ Ideal"],
    marker: { symbol: "diamond", size: 9, color: SEMANTIC_COLORS.ideal },
  });

  if (hasCoordinates(nadir, axes)) traces.push({
    x: [nadir[safe3DX]],
    y: [nadir[safe3DY]],
    z: [nadir[safe3DZ]],
    mode: "markers+text",
    type: "scatter3d",
    name: "Nadir aproximado",
    text: ["✕ Nadir aprox."],
    marker: { symbol: "cross", size: 7, color: SEMANTIC_COLORS.nadir },
  });

  [
    { key: "L1", label: "L₁", color: SEMANTIC_COLORS.L1 },
    { key: "L2", label: "L₂", color: l2Color },
    { key: "L_inf", label: "L∞", color: SEMANTIC_COLORS.L_inf },
  ].forEach((m) => {
    const sol = solutions[m.key];
    if (!sol || !hasCoordinates(sol.objectives, axes)) return;
    traces.push({
      x: [sol.objectives[safe3DX]],
      y: [sol.objectives[safe3DY]],
      z: [sol.objectives[safe3DZ]],
      mode: "markers+text",
      type: "scatter3d",
      name: m.label,
      text: [m.label],
      marker: { size: 8, color: m.color },
    });
  });

  return {
    data3D: traces,
    layout3D: {
      autosize: true,
      paper_bgcolor: paperBg,
      font: { color: textColor, size: 11 },
      scene: {
        bgcolor: plotBg,
        xaxis: { ...constantAxis(payoff, safe3DX), title: { text: headers[safe3DX] }, gridcolor: gridColor },
        yaxis: { ...constantAxis(payoff, safe3DY), title: { text: headers[safe3DY] }, gridcolor: gridColor },
        zaxis: { ...constantAxis(payoff, safe3DZ), title: { text: headers[safe3DZ] }, gridcolor: gridColor },
        camera: { eye: { x: 1.85, y: 1.85, z: 1.45 } },
        domain: { y: [0.08, 1] as [number, number] },
      },
      legend: { orientation: "h", y: -0.05, font: { size: 10 } },
      margin: { l: 0, r: 0, t: 10, b: 10 },
    },
  };
}

export function radarPlot(solveResult: SolveResponse, isDark: boolean) {
  const { paperBg, plotBg, gridColor, textColor, l2Color } = palette(isDark);
  const headers = solveResult.payoff.headers.map(escapeMarkup);
  const { solutions } = solveResult;
  const closedTheta = [...headers, headers[0]];

  const makeTrace = (key: string, name: string, color: string, fill: string) => {
    const sol = solutions[key];
    const vals = sol?.achievement_pct;
    if (headers.length < 3 || vals?.length !== headers.length || !hasCoordinates(vals, headers.map((_, i) => i))) return null;
    return {
      type: "scatterpolar",
      r: [...vals, vals[0]],
      theta: closedTheta,
      fill: "toself",
      fillcolor: fill,
      name,
      line: { color, width: 2.2 },
      marker: { size: 6, color },
    };
  };

  const traces = [
    headers.length < 3 ? null : {
      type: "scatterpolar",
      r: Array(closedTheta.length).fill(100),
      theta: closedTheta,
      name: "Ideal (100%)",
      line: { color: SEMANTIC_COLORS.ideal, width: 1.5, dash: "dash" },
      marker: { size: 4, color: SEMANTIC_COLORS.ideal },
    },
    makeTrace("L1", "L₁ (Manhattan)", SEMANTIC_COLORS.L1, "rgba(37, 99, 235, 0.12)"),
    makeTrace("L2", "L₂ (Euclidiana)", l2Color, isDark ? "rgba(203, 213, 225, 0.14)" : "rgba(51, 65, 85, 0.12)"),
    makeTrace("L_inf", "L∞ (Minimax)", SEMANTIC_COLORS.L_inf, "rgba(225, 29, 72, 0.14)"),
  ].filter(trace => trace !== null);

  return {
    dataRadar: traces,
    layoutRadar: {
      autosize: true,
      paper_bgcolor: paperBg,
      font: { color: textColor, size: 11 },
      polar: {
        bgcolor: plotBg,
        radialaxis: {
          visible: true,
          range: [Math.min(0, ...traces.flatMap(trace => trace.r)), Math.max(105, ...traces.flatMap(trace => trace.r))] as [number, number],
          ticksuffix: "%",
          gridcolor: gridColor,
          linecolor: gridColor,
        },
        angularaxis: { gridcolor: gridColor, linecolor: gridColor },
      },
      legend: { orientation: "h", y: -0.15, font: { size: 10 } },
      margin: { l: 60, r: 60, t: 42, b: 56 },
    },
  };
}

export function decisionPlot(model: ModelDefinition, solveResult: SolveResponse, isDark: boolean) {
  const { paperBg, plotBg, gridColor, textColor, l2Color } = palette(isDark);
  const v0 = model.variables[0]?.name ?? "";
  const v1 = model.variables[1]?.name ?? "";
  const poly = computeFeasiblePolygon2D(model, solveResult.payoff);
  const discretePts = computeDiscreteFeasiblePoints2D(model, solveResult.payoff);
  const isMixedInt = model.variables.some((v) => v.var_type !== "continuous");
  const traces: PlotTrace[] = [];

  if (poly?.x.every(Number.isFinite) && poly.y.every(Number.isFinite)) {
    traces.push({
      x: poly.x,
      y: poly.y,
      fill: "toself",
      fillcolor: isDark ? "rgba(15, 118, 110, 0.14)" : "rgba(15, 118, 110, 0.10)",
      line: { color: SEMANTIC_COLORS.pareto, width: isMixedInt ? 1.5 : 2, dash: isMixedInt ? "dot" : "solid" },
      mode: "lines+markers",
      marker: { size: 3, color: SEMANTIC_COLORS.pareto },
      type: "scatter",
      name: isMixedInt ? "Relajación continua" : "Región factible visible",
    });
  }

  if (discretePts?.x.every(Number.isFinite) && discretePts.y.every(Number.isFinite)) {
    traces.push({
      x: discretePts.x,
      y: discretePts.y,
      mode: "markers",
      type: "scatter",
      name: model.variables.every(v => v.var_type !== "continuous")
        ? "Muestra de puntos enteros factibles" : "Muestra mixta factible",
      marker: { size: 5.5, color: isDark ? "#38BDF8" : "#111524", opacity: 0.8 },
    });
  }

  // Óptimos independientes
  const variableKeys = [v0, v1];
  const indSols = (solveResult.payoff.independent_solutions ?? []).flatMap((values, index) =>
    hasCoordinates(values, variableKeys) ? [{ values, index }] : []);
  if (indSols.length > 0) {
    traces.push({
      x: indSols.map(({ values }) => values[v0]),
      y: indSols.map(({ values }) => values[v1]),
      mode: "markers+text",
      type: "scatter",
      name: "Óptimos Individuales",
      text: indSols.map(({ index: idx }) => `x*(Z${idx + 1})`),
      textposition: "bottom left",
      textfont: { color: SEMANTIC_COLORS.ideal, size: 10 },
      marker: { symbol: "star-open", size: 11, color: SEMANTIC_COLORS.ideal, line: { width: 2 } },
    });
  }

  const decSpanX = poly && poly.x.length ? Math.max(1e-6, Math.max(...poly.x) - Math.min(...poly.x)) : 1;
  const decSpanY = poly && poly.y.length ? Math.max(1e-6, Math.max(...poly.y) - Math.min(...poly.y)) : 1;
  const decMetricDefs = [
    { key: "L1", label: "L₁", color: SEMANTIC_COLORS.L1, symbol: "square", pos: "top right" },
    { key: "L2", label: "L₂", color: l2Color, symbol: "circle", pos: "bottom right" },
    { key: "L_inf", label: "L∞", color: SEMANTIC_COLORS.L_inf, symbol: "diamond", pos: "top left" },
  ];
  decMetricDefs.forEach((m, idxM) => {
    const sol = solveResult.solutions[m.key];
    if (!sol || !hasCoordinates(sol.variables, variableKeys)) return;
    const sx = sol.variables[v0];
    const sy = sol.variables[v1];
    const dupEarlier = decMetricDefs.slice(0, idxM).some((prev) => {
      const ps = solveResult.solutions[prev.key];
      return (
        ps?.variables &&
        Math.abs(ps.variables[v0] - sx) < 1e-3 * decSpanX &&
        Math.abs(ps.variables[v1] - sy) < 1e-3 * decSpanY
      );
    });
    const coLocated = decMetricDefs
      .filter((other) => {
        const os = solveResult.solutions[other.key];
        return (
          os?.variables &&
          Math.abs(os.variables[v0] - sx) < 1e-3 * decSpanX &&
          Math.abs(os.variables[v1] - sy) < 1e-3 * decSpanY
        );
      })
      .map((o) => o.label);

    traces.push({
      x: [sx],
      y: [sy],
      mode: dupEarlier ? "markers" : "markers+text",
      type: "scatter",
      name: `Solución ${m.label}`,
      text: dupEarlier ? undefined : [`${coLocated.join(" = ")} (${fmtNum(sx, 1)}, ${fmtNum(sy, 1)})`],
      textposition: m.pos,
      cliponaxis: false,
      textfont: { color: m.color, size: 11 },
      marker: { symbol: m.symbol, size: 13, color: m.color, line: { color: "#FFFFFF", width: 1.5 } },
    });
  });

  return {
    dataDec: traces,
    layoutDec: {
      autosize: true,
      paper_bgcolor: paperBg,
      plot_bgcolor: plotBg,
      font: { color: textColor, size: 11 },
      xaxis: { title: { text: escapeMarkup(v0) }, gridcolor: gridColor, zerolinecolor: gridColor },
      yaxis: { title: { text: escapeMarkup(v1) }, gridcolor: gridColor, zerolinecolor: gridColor },
      legend: { orientation: "h", y: -0.22, font: { size: 10 } },
      margin: { l: 58, r: 48, t: 22, b: 68 },
    },
  };
}
