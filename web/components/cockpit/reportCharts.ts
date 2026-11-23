import type { Data, Layout } from "plotly.js-dist-min";
import { decisionPlot, objectivePlot2D, objectivePlot3D, radarPlot, validParetoPoints } from "./resultFigures";
import { ModelDefinition, SolveResponse } from "./types";
import { sensitivityCurves, sensitivityLayout, sensitivitySelection } from "./weightSensitivity";

type Figure = {
  title: string;
  caption: string;
  data: unknown[];
  layout: Partial<Layout>;
};
type ChartImage = Pick<Figure, "title" | "caption"> & { png: string };

const WIDTH = 1140;
const HEIGHT = 650;
const cartesianLegend = { orientation: "h", y: -0.19, entrywidthmode: "fraction", entrywidth: 0.245 } as const;

export async function renderReportCharts(
  model: ModelDefinition,
  result: SolveResponse,
  axes2d: [number, number],
  axes3d: [number, number, number],
  signal?: AbortSignal,
): Promise<{ charts: ChartImage[]; warnings: string[] }> {
  const charts: ChartImage[] = [];
  const warnings: string[] = [];
  const figures: Figure[] = [];
  const headers = result.payoff.headers;
  const objectiveLabels = (axes: number[]) => axes.map(i => `Z${i + 1} = ${headers[i]}`).join(" · ");
  const hasClippedRanges = result.payoff.decision_ranges_2d?.some(([lo, hi]) => lo === null || hi === null);
  const boundsNote = hasClippedRanges ? " La región visible se recorta en los ejes sin cota finita confirmada." : "";
  const hasPareto = validParetoPoints(result).length > 0;
  const { data2D, layout2D } = objectivePlot2D(model, result, axes2d, false, {
    showPareto: true, showFeasibleObj: true, showIsodistance: true,
  });
  const hasContours = data2D.some(trace => String(trace.name).startsWith("Iso "));
  if (data2D.length) figures.push({
    title: "Espacio de objetivos 2D",
    caption: objectiveLabels(axes2d) + ". " + [
      hasPareto && "Muestras Pareto",
      hasContours && (headers.length === 2 ? "curvas de isodistancia" : "curvas de isodistancia en los dos ejes"),
      "soluciones y puntos de referencia",
    ].filter(Boolean).join(" · ") + "." + boundsNote,
    data: data2D,
    layout: {
      ...layout2D,
      xaxis: { ...layout2D.xaxis, title: { text: `Z${axes2d[0] + 1}` } },
      yaxis: { ...layout2D.yaxis, title: { text: `Z${axes2d[1] + 1}` } },
      legend: cartesianLegend,
      margin: { b: 170 },
    },
  });
  else warnings.push("Espacio de objetivos 2D: no hay coordenadas válidas.");
  if (model.variables.length === 2) {
    const { dataDec, layoutDec } = decisionPlot(model, result, false);
    if (dataDec.length) {
      figures.push({
        title: "Región de decisiones",
        caption: model.variables.map((variable, i) => `x${i + 1} = ${variable.name}`).join(" · ") + "." + boundsNote,
        data: dataDec,
        layout: {
          ...layoutDec,
          xaxis: { ...layoutDec.xaxis, title: { text: "x1" } },
          yaxis: { ...layoutDec.yaxis, title: { text: "x2" } },
          legend: cartesianLegend,
          margin: { b: 150 },
        },
      });
    } else {
      warnings.push("Región de decisiones: el cálculo no devolvió datos para dibujarla.");
    }
  }

  const sweep = result.weight_sensitivity;
  if (headers.length === 2) {
    const curves = sweep ? sensitivityCurves({ ...sweep, objective_names: ["Z1", "Z2"] }, false) : [];
    if (curves.length) {
      const selection = sensitivitySelection(result, result.weights[0], false);
      figures.push({
        title: "Sensibilidad de pesos",
        caption: objectiveLabels([0, 1]) + ". La línea punteada indica el peso usado en este cálculo.",
        data: [...curves, ...selection.traces],
        layout: { ...sensitivityLayout(false, false), shapes: selection.shapes, margin: { l: 100, r: 88, t: 50, b: 120 }, legend: { orientation: "h", y: -0.14 } } as Partial<Layout>,
      });
    } else {
      warnings.push("Sensibilidad de pesos: el motor no devolvió muestras que se puedan graficar.");
    }
  } else if (headers.length >= 3) {
    const { data3D, layout3D } = objectivePlot3D(result, axes3d, false, true);
    const labelPositions: Record<string, string> = { "L₁": "top right", "L₂": "bottom right", "L∞": "top left" };
    if (data3D.length) figures.push({
      title: "Espacio de objetivos 3D",
      caption: objectiveLabels(axes3d) + ". Proyección tridimensional de las soluciones y las referencias"
        + (hasPareto ? " con muestras de la frontera de Pareto." : "."),
      data: data3D.map(trace => {
        const textposition = labelPositions[String(trace.name)];
        return textposition ? { ...trace, textposition } : trace;
      }),
      layout: {
        ...layout3D,
        margin: { l: 70, r: 70, t: 36, b: 105 },
        scene: {
          ...layout3D.scene,
          camera: { eye: { x: 1.53, y: 1.53, z: 1.29 } },
          xaxis: { ...layout3D.scene.xaxis, title: { text: `Z${axes3d[0] + 1}` }, nticks: 5, tickfont: { size: 14 } },
          yaxis: { ...layout3D.scene.yaxis, title: { text: `Z${axes3d[1] + 1}` }, nticks: 5, tickfont: { size: 14 } },
          zaxis: { ...layout3D.scene.zaxis, title: { text: `Z${axes3d[2] + 1}` }, nticks: 5, tickfont: { size: 14 } },
        },
        legend: { orientation: "h", y: -0.04 },
      },
    });

    if (!data3D.length) warnings.push("Espacio de objetivos 3D: no hay coordenadas válidas.");
    const { dataRadar, layoutRadar } = radarPlot(result, false);
    if (dataRadar.length > 1) {
      const theta = headers.map((_, i) => `Z${i + 1}`);
      figures.push({
        title: "Radar de logro por objetivo",
        caption: objectiveLabels(headers.map((_, i) => i)) + ". El contorno de referencia representa un logro del 100 %.",
        data: dataRadar.map(trace => ({ ...trace, theta: [...theta, theta[0]] })),
        layout: { ...layoutRadar, margin: { l: 100, r: 88, t: 50, b: 110 }, legend: { orientation: "h", y: -0.10 } },
      });
    } else {
      warnings.push("Radar de logro: las soluciones no incluyen porcentajes de logro.");
    }
  }

  signal?.throwIfAborted();
  const Plotly = await import("plotly.js-dist-min").then(module => module.default);
  const frame = document.createElement("div");
  frame.setAttribute("aria-hidden", "true");
  frame.style.cssText = `position:fixed;left:-${WIDTH + 50}px;top:0;width:${WIDTH}px;height:${HEIGHT}px;pointer-events:none;`;
  document.body.append(frame);
  try {
    for (const { title, caption, data, layout } of figures) {
      signal?.throwIfAborted();
      const plot = document.createElement("div");
      frame.append(plot);
      try {
        await Plotly.newPlot(plot, data as Data[], {
          ...layout,
          autosize: false,
          width: WIDTH,
          height: HEIGHT,
          font: { ...layout.font, size: 17 },
          margin: { l: 100, r: 88, t: 50, b: 120, ...layout.margin },
          legend: { ...layout.legend, x: 0, xanchor: "left", font: { size: 15 } },
        }, { staticPlot: true, displayModeBar: false, displaylogo: false });
        const dataUrl = await Plotly.toImage(plot, { format: "png", width: WIDTH, height: HEIGHT, scale: 1.5 });
        const prefix = "data:image/png;base64,";
        if (!dataUrl.startsWith(prefix)) throw new Error("Formato de captura inesperado.");
        charts.push({ title, caption, png: dataUrl.slice(prefix.length) });
      } catch {
        warnings.push(`${title}: el navegador no pudo generar la imagen.`);
      } finally {
        try { Plotly.purge(plot); } finally { plot.remove(); }
      }
    }
  } finally {
    frame.remove();
  }
  return { charts, warnings };
}
