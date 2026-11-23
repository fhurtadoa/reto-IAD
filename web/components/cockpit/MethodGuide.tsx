import type { ReactNode } from "react";
import KatexBlock from "./KatexBlock";
import SectionHeading from "./SectionHeading";
import { buildLinfXRayLatex, cleanDeviation, fmtAchievement, fmtNum } from "./mathUtils";
import type { ModelDefinition, SolveResponse } from "./types";

function MethodTable({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="method-table-frame cockpit-scroll" role="region" tabIndex={0} aria-label={label}>
      <table className="data-table method-table">
        <caption className="sr-only">{label}</caption>
        {children}
      </table>
    </div>
  );
}

const steps = [
  ["referencias", "Referencias"],
  ["escala", "Normalización"],
  ["metricas", "Métricas"],
] as const;

const metrics = [
  { key: "L1", name: "L₁ · Manhattan", formula: String.raw`D_1=\sum_i w_i D_i`, note: "Minimiza la suma de brechas ponderadas. Con pesos que suman 1, equivale a maximizar la suma ponderada de logros expresados como proporciones." },
  { key: "L2", name: "L₂ · Euclidiana", formula: String.raw`D_2=\sqrt{\sum_i (w_i D_i)^2}`, note: "Multiplica cada brecha por su peso y luego eleva el producto al cuadrado." },
  { key: "L_inf", name: "L∞ · Minimax", formula: String.raw`D_\infty=\max_i(w_iD_i)`, note: "Reduce la mayor brecha ponderada." },
] as const;

export default function MethodGuide({ model, result }: { model: ModelDefinition; result: SolveResponse }) {
  const { payoff, solutions, weights } = result;
  const { headers, matrix, ideal_point: ideal, anti_ideal_point: nadir } = payoff;
  const ranges = headers.map((_, i) => payoff.normalization_ranges?.[i] ?? (Math.abs(ideal[i] - nadir[i]) || 1));
  const rangeLabels = {
    payoff: "Matriz de pagos",
    feasible_range: "Rango factible",
    constant: "Objetivo constante",
    unit: "Una unidad del objetivo",
  };
  const deviation = (value: number, i: number) => {
    if (payoff.normalization_sources?.[i] === "constant") return 0;
    const gap = model.objectives[i].sense === "minimize" ? value - ideal[i] : ideal[i] - value;
    return Math.max(0, gap / ranges[i]);
  };
  const minimax = solutions.L_inf;
  const hasMinimax = Boolean(minimax?.objectives?.length);
  const firstMinimaxDeviation = cleanDeviation(minimax?.normalized_distances?.[0]);
  const firstMinimaxAchievement = minimax?.achievement_pct?.[0];
  const xray = buildLinfXRayLatex(model, payoff, weights, hasMinimax ? minimax : undefined);

  return (
    <article className="method-guide" aria-labelledby="workspace-section-title">
      <header className="method-header">
        <p>Primero se construyen las referencias de cada objetivo. Después se expresa cada brecha en una escala común y se aplica la preferencia del decisor.</p>
        <nav className="method-index" aria-label="En esta explicación">
          {steps.map(([id, title], i) => <a href={`#metodo-${id}`} key={id}><span>{i + 1}</span>{title}</a>)}
        </nav>
      </header>

      <section className="method-step" id="metodo-referencias" aria-labelledby="method-references">
        <SectionHeading level="h3" id="method-references" title="1. Construir las referencias"
          cue="Qué se alcanza al optimizar cada objetivo por separado" />
        <p>Lee cada fila como una solución distinta. La diagonal reúne el ideal. El peor valor observado de cada columna sirve como nadir aproximado. El nadir teórico toma los peores valores del conjunto eficiente y el antiideal toma los peores de toda la región factible. Cuando hay varios óptimos individuales, el motor desempata mejorando la suma de los otros objetivos escalados.</p>
        <h4>Matriz de pagos</h4>
        <p className="method-scroll-hint">Desliza la tabla hacia los lados para ver todos los objetivos.</p>
        <MethodTable label="Matriz de pagos y vectores de referencia">
          <thead><tr><th scope="col">Objetivo optimizado</th>{headers.map((name, i) => (
            <th scope="col" key={i}><span className="table-symbol">Z{i + 1}</span>{name}</th>
          ))}</tr></thead>
          <tbody>{matrix.map((row, i) => (
            <tr key={i}><th scope="row">Z{i + 1} · {headers[i]}</th>{row.map((value, j) => (
              <td className={i === j ? "reference-ideal" : undefined} key={j}>
                {i === j && <span className="sr-only">Óptimo individual </span>}{fmtNum(value, 4)}
              </td>
            ))}</tr>
          ))}</tbody>
          <tfoot>
            <tr className="reference-ideal"><th scope="row">Ideal</th>{ideal.map((value, i) => <td key={i}>{fmtNum(value, 4)}</td>)}</tr>
            <tr className="reference-nadir"><th scope="row">Nadir aproximado</th>{nadir.map((value, i) => <td key={i}>{fmtNum(value, 4)}</td>)}</tr>
          </tfoot>
        </MethodTable>
      </section>

      <section className="method-step" id="metodo-escala" aria-labelledby="method-scale">
        <SectionHeading level="h3" id="method-scale" title="2. Medir la brecha al ideal"
          cue="Una escala común para objetivos con unidades distintas" />
        <div className="method-equations">
          <div><h4>Desviación normalizada</h4><KatexBlock latex={String.raw`D_i(x)=\begin{cases}
            (Z_i^*-Z_i(x))/R_i & \text{al maximizar}\\
            (Z_i(x)-Z_i^*)/R_i & \text{al minimizar}
          \end{cases}`} /></div>
          <div><h4>Porcentaje de logro</h4><KatexBlock latex={String.raw`Z'_i(x)=100(1-D_i(x))\,\%`} />
            <p>100 % corresponde al ideal. Con rango de pagos positivo, la referencia equivale a 0 % y un resultado peor da un logro negativo.</p></div>
        </div>
        <p>Para cada criterio, el rango Rᵢ es la diferencia absoluta entre el ideal y el nadir aproximado. Si ambos coinciden, se usa el rango factible cuando es finito y positivo. Un criterio constante tiene brecha cero. Si no se puede calcular el peor valor factible, se usa una unidad del objetivo como escala auxiliar.</p>
        <MethodTable label="Rangos de normalización y preferencias del modelo">
          <thead><tr><th scope="col">Objetivo</th><th scope="col">Sentido</th><th scope="col">Rango Rᵢ</th><th scope="col">Base de la escala</th><th scope="col">Peso wᵢ</th></tr></thead>
          <tbody>{headers.map((name, i) => <tr key={i}>
            <th scope="row">Z{i + 1} · {name}</th><td>{model.objectives[i].sense === "minimize" ? "Minimizar" : "Maximizar"}</td>
            <td>{payoff.normalization_sources?.[i] === "constant" ? "—" : fmtNum(ranges[i], 6)}</td>
            <td>{rangeLabels[payoff.normalization_sources?.[i] ?? "payoff"]}</td><td>{fmtNum(weights[i] * 100, 2)} %</td>
          </tr>)}</tbody>
        </MethodTable>
        {hasMinimax && (
          <p className="method-example">
            <strong>Ejemplo con L∞ · {headers[0]}.</strong>{" "}
            El valor {fmtNum(minimax.objectives[0], 4)} da una desviación de {firstMinimaxDeviation === undefined ? "—" : `${fmtNum(100 * firstMinimaxDeviation, 2)} %`}
            {" "}y un logro de {fmtAchievement(firstMinimaxAchievement, 2)}.
          </p>
        )}
        <details className="method-disclosure">
          <summary>Consultar matriz de pagos normalizada</summary>
          <p>La misma matriz expresada como desviaciones Dᵢ. Cero indica el ideal. Uno indica el nadir cuando el rango observado es positivo.</p>
          <MethodTable label="Matriz de pagos normalizada">
            <thead><tr><th scope="col">Objetivo optimizado</th>{headers.map((name, i) => <th scope="col" key={i}>D{i + 1} · {name}</th>)}</tr></thead>
            <tbody>{matrix.map((row, i) => <tr key={i}><th scope="row">Z{i + 1} · {headers[i]}</th>
              {row.map((value, j) => <td key={j}>{fmtNum(cleanDeviation(deviation(value, j)), 3)}</td>)}</tr>)}</tbody>
          </MethodTable>
        </details>
      </section>

      <section className="method-step" id="metodo-metricas" aria-labelledby="method-metrics">
        <SectionHeading level="h3" id="method-metrics" title="3. Resolver y comparar"
          cue="Tres maneras de ponderar la distancia al ideal" />
        <p>Cada métrica se minimiza con las restricciones y dominios del modelo. Compara los valores y logros por objetivo, porque cada distancia se calcula con una fórmula distinta.</p>
        <div className="method-metrics">{metrics.map(({ key, name, formula, note }) => (
          <div key={key}><h4>{name}</h4><KatexBlock latex={formula} /><p>{note}</p>
            <p className="method-distance">Distancia calculada <strong>{solutions[key]?.objectives?.length ? fmtNum(solutions[key].aggregate_distance, 4) : "—"}</strong>
              {solutions[key]?.status === "feasible_suboptimal" && <span> · Factible sin certificado</span>}</p></div>
        ))}</div>
        <div className="method-equation method-minimax">
          <div><h4>Cómo se linealiza el minimax</h4>
          <p>λ acota todas las brechas ponderadas. Minimizar λ equivale a minimizar su máximo. Cada brecha que alcanza λ es activa. Puede haber una sola, por ejemplo cuando las cantidades deben ser enteras. En caso de empate el motor minimiza la suma de brechas manteniendo λ fija.</p></div>
          <KatexBlock latex={xray.headerLatex} />
        </div>
        <details className="method-disclosure">
          <summary>Ver restricciones minimax con los datos del modelo</summary>
          <p>Los coeficientes y valores de esta vista se muestran redondeados.</p>
          {xray.constraintsLatex.map((latex, i) => (
            <div key={i} className="method-constraint">
              <h4>Z{i + 1} · {headers[i]}</h4><KatexBlock latex={latex} />
            </div>
          ))}
        </details>
      </section>
    </article>
  );
}
