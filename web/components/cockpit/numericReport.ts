import { cleanAchievement, cleanDeviation, escapeMarkup } from "./mathUtils";
import type { ModelDefinition, SolveResponse } from "./types";

const METRICS = [["L₁", "L1"], ["L₂", "L2"], ["L∞", "L_inf"]] as const;

function numeric(value: number | undefined) {
  return value !== undefined && Number.isFinite(value) ? String(value) : "—";
}

export function buildNumericReport(model: ModelDefinition, result: SolveResponse) {
  const { payoff } = result;
  const objectives = payoff.headers.map((name, i) => `Z${i + 1} · ${name}`);
  const tables = [
    {
      title: "Ponderaciones aplicadas",
      headers: ["Objetivo", "Peso"],
      rows: objectives.map((name, i) => [name, numeric(result.weights[i])]),
    },
    {
      title: "Matriz de pagos",
      headers: ["Objetivo optimizado", ...objectives],
      rows: [
        ...payoff.matrix.map((row, i) => [objectives[i] ?? "—", ...row.map(numeric)]),
        ["Ideal", ...payoff.ideal_point.map(numeric)],
        ["Nadir aproximado", ...payoff.anti_ideal_point.map(numeric)],
      ],
    },
    {
      title: "Distancias agregadas",
      headers: ["Métrica", "Dₚ"],
      rows: METRICS.map(([name, key]) => {
        const solution = result.solutions[key];
        return [name, numeric(solution?.objectives?.length ? solution.aggregate_distance : undefined)];
      }),
    },
    {
      title: "Comparación por objetivo",
      headers: ["Objetivo", "Métrica", "Valor Zᵢ", "Desviación Dᵢ", "% de logro"],
      rows: objectives.flatMap((name, i) => METRICS.map(([metric, key]) => {
        const solution = result.solutions[key];
        return [
          name, metric, numeric(solution?.objectives?.[i]),
          numeric(cleanDeviation(solution?.normalized_distances?.[i])),
          numeric(cleanAchievement(solution?.achievement_pct?.[i])),
        ];
      })),
    },
    {
      title: "Valores de las variables",
      headers: ["Variable", ...METRICS.map(([name]) => name)],
      rows: model.variables.map(({ name }) => [
        name, ...METRICS.map(([, key]) => numeric(result.solutions[key]?.variables?.[name])),
      ]),
    },
  ];
  const oneLine = (value: string) => value.replace(/\s+/g, " ").trim();
  const escapeHtml = (value: string) => escapeMarkup(oneLine(value));
  const escapeMarkdown = (value: string) => oneLine(value).replace(/[\\|`*_\[\]~]/g, "\\$&");
  const markdownRow = (row: string[]) => `| ${row.map(escapeMarkdown).join(" | ")} |`;
  const title = model.name || "Modelo sin título";
  const markdown = [
    `# ${escapeMarkdown(title)}`,
    ...tables.map(({ title, headers, rows }) =>
      [`## ${title}`, "", markdownRow(headers), markdownRow(headers.map(() => "---")), ...rows.map(markdownRow)].join("\n")),
  ].join("\n\n");
  const html = [
    `<h1>${escapeHtml(title)}</h1>`,
    ...tables.map(({ title, headers, rows }) =>
      `<h2>${title}</h2><table><thead><tr>${headers.map(cell => `<th>${escapeHtml(cell)}</th>`).join("")}</tr></thead>`
      + `<tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>`),
  ].join("");
  return { markdown, html };
}
