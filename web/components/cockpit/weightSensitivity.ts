import { escapeMarkup, fmtNum } from "./mathUtils";
import { SolveResponse, WeightSensitivityData } from "./types";

const panels = [
  ["l1", "L1", "L₁ · Manhattan"],
  ["l2", "L2", "L₂ · Euclidiana"],
  ["l_inf", "L_inf", "L∞ · Minimax"],
] as const;

const hover = "w₁ %{x:.3f} · w₂ %{customdata[0]:.3f}<br>Valor %{customdata[1]}<br>Desviación %{y:.2f}%<br>%{customdata[2]}<extra>%{fullData.name}</extra>";

export function sensitivityCurves(sweep: WeightSensitivityData, dark: boolean) {
  const colors = dark ? ["#7dd3fc", "#fdba74"] : ["#0369a1", "#b45309"];
  return panels.flatMap(([key], panel) => {
    const samples = (sweep[key] ?? []).filter(p => Number.isFinite(p?.w1));
    return colors.flatMap((color, i) => {
      const values = samples.map(p => {
        const deviation = p.deviations_pct?.[i];
        return Number.isFinite(deviation) ? deviation : null;
      });
      if (!values.some(value => value !== null)) return [];
      return [{
        type: "scatter",
        mode: "lines+markers",
        name: escapeMarkup(sweep.objective_names?.[i] ?? ("Z" + (i + 1))),
        legendgroup: String(i),
        showlegend: panel === 0,
        xaxis: panel ? `x${panel + 1}` : "x",
        yaxis: panel ? `y${panel + 1}` : "y",
        x: samples.map(p => p.w1),
        y: values,
        customdata: samples.map(p => [Number.isFinite(p.weights?.[1]) ? p.weights[1] : null, fmtNum(p.objectives?.[i], 4),
        p.status === "optimal" ? "Óptimo" : "Factible sin certificado"]),
        hovertemplate: hover,
        connectgaps: false,
        line: { color, dash: i ? "dash" : "solid", shape: key === "l1" ? "hv" : "linear" },
        marker: { color, symbol: i ? "square" : "circle", size: 5 },
      }];
    });
  });
}

export function sensitivitySelection(result: SolveResponse, selected: number | null, dark: boolean) {
  const colors = dark ? ["#7dd3fc", "#fdba74"] : ["#0369a1", "#b45309"];
  const traces = panels.flatMap(([, metric], panel) => colors.flatMap((color, i) => {
    const solution = result.solutions[metric];
    const deviation = (solution?.normalized_distances?.[i] ?? NaN) * 100;
    if (!solution || !Number.isFinite(deviation) || !Number.isFinite(result.weights?.[0])) return [];
    return [{
      type: "scatter",
      mode: "markers",
      name: escapeMarkup(result.payoff.headers[i] ?? ("Z" + (i + 1))),
      showlegend: false,
      xaxis: panel ? `x${panel + 1}` : "x",
      yaxis: panel ? `y${panel + 1}` : "y",
      x: [result.weights[0]],
      y: [deviation],
      customdata: [[Number.isFinite(result.weights[1]) ? result.weights[1] : null, fmtNum(solution.objectives?.[i], 4),
      solution.status === "optimal" ? "Último cálculo · Óptimo" : "Último cálculo · Factible sin certificado"]],
      hovertemplate: hover,
      marker: { color, symbol: i ? "square" : "circle", size: 11, line: { color: dark ? "#111524" : "#fff", width: 2 } },
    }];
  }));
  const shapes = selected === null || !Number.isFinite(selected) ? [] : panels.map((_, i) => ({
    type: "line", xref: i ? `x${i + 1}` : "x", yref: i ? `y${i + 1} domain` : "y domain",
    x0: selected, x1: selected, y0: 0, y1: 1,
    line: { color: dark ? "#fda4af" : "#9f1239", dash: "dot", width: 2 },
  }));
  return { traces, shapes };
}

export function sensitivityLayout(stacked: boolean, dark: boolean) {
  const axes: Record<string, unknown> = {};
  const gridcolor = dark ? "#334155" : "#e2e8f0";
  const annotations = panels.map(([, , title], i) => {
    const x0 = stacked ? 0 : i * 0.351;
    const x1 = stacked || i === 2 ? 1 : x0 + 0.295;
    const y1 = stacked ? 0.96 - i * 0.34 : 0.93;
    const y0 = stacked ? y1 - 0.26 : 0;
    const suffix = i ? String(i + 1) : "";
    axes[`xaxis${suffix}`] = {
      domain: [x0, x1], anchor: `y${suffix}`, range: [-0.015, 1.015],
      tickvals: [0, 0.25, 0.5, 0.75, 1], gridcolor, title: { text: !stacked || i === 2 ? "Peso w₁" : "" },
    };
    axes[`yaxis${suffix}`] = {
      domain: [y0, y1], anchor: `x${suffix}`, matches: i ? "y" : undefined,
      ticksuffix: "%", gridcolor, title: { text: !i || stacked ? "Desviación al ideal" : "" },
    };
    return { x: (x0 + x1) / 2, y: y1, xref: "paper", yref: "paper", yshift: 13, showarrow: false, text: title, font: { size: 13 } };
  });
  return {
    ...axes, annotations, autosize: true, height: stacked ? 830 : 380,
    paper_bgcolor: dark ? "#111524" : "#fff",
    plot_bgcolor: dark ? "#1e293b" : "#f8fafc",
    font: { color: dark ? "#e2e8f0" : "#0f172a", size: 11 },
    margin: { t: 20, b: 70, l: 62, r: 18 },
    legend: { orientation: "h", x: 0, y: stacked ? -0.06 : -0.2 },
  };
}
