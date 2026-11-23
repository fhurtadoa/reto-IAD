import {
  ModelDefinition,
  ObjectiveModel,
  ConstraintModel,
  ConstraintSense,
  ObjectiveSense,
  PayoffMatrixData,
  MetricSolution,
  SolveResponse,
} from "./types";

/**
 * Formatea un número compacto para visualización en tablas (locale es-CO).
 */
export function fmtNum(val: number | undefined | null, decimals = 2): string {
  if (val === undefined || val === null || !Number.isFinite(val)) return "—";
  if (val === 0) return "0";
  if (Math.abs(val) >= 10000) {
    return val.toLocaleString("es-CO", { maximumFractionDigits: Math.min(decimals, 1) });
  }
  if (val !== 0 && Number(val.toFixed(decimals)) === 0) {
    return val.toLocaleString("es-CO", { notation: "scientific", maximumSignificantDigits: 4 });
  }
  const rounded = Number(val.toFixed(decimals));
  return (Object.is(rounded, -0) ? 0 : val).toLocaleString("es-CO", { maximumFractionDigits: decimals });
}

const DISPLAY_EPSILON = 1e-9;

export function cleanDeviation(value: number | undefined): number | undefined {
  return value !== undefined && Math.abs(value) < DISPLAY_EPSILON ? 0 : value;
}

export function cleanAchievement(value: number | undefined): number | undefined {
  return value !== undefined && Math.abs(value - 100) < DISPLAY_EPSILON ? 100 : cleanDeviation(value);
}

export function fmtAchievement(value: number | undefined, decimals = 1): string {
  const clean = cleanAchievement(value);
  return clean === undefined || !Number.isFinite(clean) ? "—" : `${fmtNum(clean, decimals)} %`;
}

export function hasFeasibleSolution(result: SolveResponse): boolean {
  return Object.values(result.solutions).some(solution =>
    ["optimal", "feasible_suboptimal"].includes(solution.status) &&
    solution.objectives.length === result.payoff.headers.length &&
    solution.objectives.length > 0
  );
}

/**
 * Formatea números limpios para KaTeX/LaTeX (punto decimal estándar y separador fino \, para miles,
 * evitando la coma española que genera espacios extra en modo matemático).
 */
export function fmtLatexNum(val: number | undefined | null, decimals: number | null = 2): string {
  if (val === undefined || val === null || !Number.isFinite(val) || val === 0) return "0";
  const rounded = decimals === null ? val : Number(val.toFixed(Math.abs(val) >= 10000 ? Math.min(decimals, 1) : decimals));
  if ((rounded === 0 && val !== 0) || String(rounded).includes("e")) {
    const [mantissa, exponent] = val.toExponential(decimals ?? undefined).split("e");
    return `${Number(mantissa)} \\times 10^{${Number(exponent)}}`;
  }
  const [intPart, decPart] = String(rounded).split(".");
  const sign = intPart.startsWith("-") ? "-" : "";
  const digits = intPart.replace("-", "");
  const withSep = digits.replace(/\B(?=(\d{3})+(?!\d))/g, "\\,");
  return decPart ? `${sign}${withSep}.${decPart}` : `${sign}${withSep}`;
}

export function duplicateVarPrefixes(varNames: string[]): Set<string> {
  const counts = new Map<string, number>();
  varNames.forEach((raw) => {
    const head = raw.trim().split(/\s+/)[0];
    counts.set(head, (counts.get(head) ?? 0) + 1);
  });
  return new Set(Array.from(counts.entries()).filter(([, c]) => c > 1).map(([k]) => k));
}

/**
 * Formatea una combinación lineal en texto plano o LaTeX.
 */
export function formatLinearExpr(
  coeffs: number[],
  varNames: string[],
  asLatex = false
): string {
  const dupPrefixes = asLatex ? duplicateVarPrefixes(varNames) : new Set<string>();
  const parts: string[] = [];
  for (let i = 0; i < varNames.length; i++) {
    const c = coeffs[i] ?? 0;
    if (c === 0) continue;
    const absC = Math.abs(c);
    const vRaw = varNames[i];
    const head = vRaw.trim().split(/\s+/)[0];
    const vStr = asLatex ? formatVarLatex(vRaw, dupPrefixes.has(head)) : vRaw;
    const coeffStr = absC === 1 ? "" : `${asLatex ? fmtLatexNum(absC, null) : absC}${asLatex ? "\\," : "*"}`;
    if (parts.length === 0) {
      parts.push(c < 0 ? `-${coeffStr}${vStr}` : `${coeffStr}${vStr}`);
    } else {
      parts.push(c < 0 ? ` - ${coeffStr}${vStr}` : ` + ${coeffStr}${vStr}`);
    }
  }
  return parts.length > 0 ? parts.join("") : "0";
}

export function escapeMarkup(text: string): string {
  return text.replace(/[&<>]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[character]!);
}

function escapeLatexText(text: string): string {
  const specials: Record<string, string> = {
    "\\": "\\textbackslash{}", "^": "\\textasciicircum{}", "~": "\\textasciitilde{}",
  };
  return text.replace(/[\\^~_{}%$&#]/g, character => specials[character] ?? "\\" + character);
}

export function formatVarLatex(name: string, disambiguate = false): string {
  // Convierte x1 -> x_{1}, x_1_2 -> x_{1,2}
  const trimmed = name.trim();
  const spaceIdx = trimmed.search(/\s/);
  const clean = spaceIdx === -1 ? trimmed : trimmed.slice(0, spaceIdx);
  const tail = spaceIdx === -1 ? "" : trimmed.slice(spaceIdx).trim();
  const match = clean.match(/^([a-zA-Z]+)_?([0-9]+(?:_[0-9]+)*)$/);
  const base = match
    ? `${match[1]}_{${match[2].replace(/_/g, ",")}}`
    : `\\text{${escapeLatexText(clean)}}`;
  if (!disambiguate || !tail) return base;
  return `${base}\\,\\text{${escapeLatexText(tail)}}`;
}

/**
 * Convierte un ModelDefinition a texto algebraico editable.
 */
function algebraicVariableTokens(model: ModelDefinition): string[] {
  const names = model.variables.map((v) => v.name.trim().split(/\s+/)[0]);
  const reserved = new Set(names);
  return names.map((name, i) => {
    if (/^[a-zA-Z][a-zA-Z0-9_]*$/.test(name) && names.indexOf(name) === names.lastIndexOf(name)) return name;
    let token = `var_${i + 1}`;
    while (reserved.has(token)) token += "_";
    return token;
  });
}

export function modelToAlgebraicText(model: ModelDefinition): string {
  const varNames = algebraicVariableTokens(model);
  const lines: string[] = [];

  model.objectives.forEach((obj, idx) => {
    const sense = obj.sense === "maximize" ? "Max" : "Min";
    const expr = formatLinearExpr(obj.coefficients, varNames, false);
    lines.push(`${sense} Z${idx + 1} (${obj.name}) = ${expr}`);
  });

  lines.push("s.a.");

  model.constraints.forEach((c) => {
    const expr = formatLinearExpr(c.coefficients, varNames, false);
    const sense = c.sense === "==" ? "=" : c.sense;
    lines.push(`${expr} ${sense} ${c.rhs}`);
  });

  return lines.join("\n");
}

export interface AlgebraicParseResult {
  ok: boolean;
  objectives?: ObjectiveModel[];
  constraints?: ConstraintModel[];
  detectedVariables?: string[];
  errors: string[];
}

/**
 * Parsea un bloque de texto algebraico en objetivos y restricciones lineales.
 * Soporta constantes aditivas, variables en ambos lados de las restricciones,
 * paréntesis anidados en nombres de objetivos y comas decimales.
 * Retorna errores detallados en español si hay sintaxis inválida.
 */
export function parseAlgebraicModel(
  text: string,
  existingModel: ModelDefinition
): AlgebraicParseResult {
  const errors: string[] = [];
  const rawLines = text.split(/\r?\n/)
    .map((raw, index) => ({ line: raw.trim(), lineNo: index + 1 }))
    .filter(({ line }) => line && !line.startsWith("#") && !line.startsWith("//"));

  if (rawLines.length === 0) {
    return { ok: false, errors: ["El editor algebraico está vacío. Ingresa al menos 2 objetivos."] };
  }

  const existingTokens = algebraicVariableTokens(existingModel);
  const tokenToFullName = new Map(existingTokens.map((token, i) => [token, existingModel.variables[i].name]));
  const encountered = new Set<string>();

  const parseConstFactor = (raw: string): number | null => {
    const numPattern = "(?:\\d+(?:\\.\\d+)?|\\.\\d+)(?:[eE][+-]?\\d+)?";
    const direct = new RegExp(`^[+-]?${numPattern}$`);
    if (direct.test(raw)) {
      const val = parseFloat(raw);
      return Number.isFinite(val) ? val : null;
    }
    const fracParen = new RegExp(`^\\(\\s*([+-]?${numPattern})\\s*\\/\\s*([+-]?${numPattern})\\s*\\)$`);
    const fracBare = new RegExp(`^([+-]?${numPattern})\\s*\\/\\s*([+-]?${numPattern})$`);
    const fm = raw.match(fracParen) ?? raw.match(fracBare);
    if (!fm) return null;
    const num = parseFloat(fm[1]);
    const den = parseFloat(fm[2]);
    if (!Number.isFinite(num) || !Number.isFinite(den) || den === 0) return null;
    const val = num / den;
    return Number.isFinite(val) ? val : null;
  };

  const parseLinearSide = (
    expr: string,
    lineNo: number
  ): { coeffsMap: Record<string, number>; constant: number } | null => {
    const clean = expr.trim()
      .replace(/[−–—]/g, "-")
      .replace(/[·×]/g, "*")
      .replace(/(\d),(?=\d)/g, "$1.");
    if (!clean) {
      errors.push(`Línea ${lineNo}: expresión vacía.`);
      return null;
    }
    if (/[^a-zA-Z0-9_+\-.*\/\s()]/.test(clean)) {
      errors.push(`Línea ${lineNo}: contiene caracteres no reconocidos en "${expr}".`);
      return null;
    }

    const coeffsMap: Record<string, number> = Object.create(null);
    let constant = 0;
    const normalized = clean.startsWith("+") || clean.startsWith("-") ? clean : `+${clean}`;
    const termRegex = /([+-])((?:[^+-]|(?<=[0-9][eE])[+-])+)/g;
    let match: RegExpExecArray | null;
    let consumed = 0;

    while ((match = termRegex.exec(normalized)) !== null) {
      consumed += match[0].length;
      const sign = match[1] === "-" ? -1 : 1;
      const body = match[2].trim();

      // Forma 1: constante numérica pura o fracción constante (ej. "+100", ".5", "1/2")
      const pureConst = parseConstFactor(body);
      if (pureConst !== null) {
        constant += sign * pureConst;
        if (!Number.isFinite(constant)) {
          errors.push(`Línea ${lineNo}: constante fuera del rango numérico "${match[0]}".`);
          return null;
        }
        continue;
      }

      // Forma 2: [const][*][var], [var], [var]*[const] o [var]/[const]
      let numVal: number | null = null;
      let varName: string | null = null;

      const mVarOnly = body.match(/^([a-zA-Z][a-zA-Z0-9_]*)$/);
      const mVarDiv = body.match(/^([a-zA-Z][a-zA-Z0-9_]*)\s*\/\s*(.+)$/);
      const mVarMul = body.match(/^([a-zA-Z][a-zA-Z0-9_]*)\s*\*\s*(.+)$/);
      const mMulPrefix = body.match(/^(.+?)\s*\*\s*([a-zA-Z][a-zA-Z0-9_]*)$/);
      const mImplicitPrefix = body.match(/^((?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Z][a-zA-Z0-9_]*)$/);

      if (mVarOnly) {
        numVal = 1.0;
        varName = mVarOnly[1];
      } else if (mVarDiv) {
        const den = parseConstFactor(mVarDiv[2].trim());
        if (den !== null && den !== 0 && Number.isFinite(1 / den)) {
          numVal = 1 / den;
          varName = mVarDiv[1];
        }
      } else if (mVarMul) {
        const factor = parseConstFactor(mVarMul[2].trim());
        if (factor !== null) {
          numVal = factor;
          varName = mVarMul[1];
        }
      } else if (mMulPrefix) {
        const factor = parseConstFactor(mMulPrefix[1].trim());
        if (factor !== null) {
          numVal = factor;
          varName = mMulPrefix[2];
        }
      } else if (mImplicitPrefix) {
        const factor = parseConstFactor(mImplicitPrefix[1].trim());
        if (factor !== null) {
          numVal = factor;
          varName = mImplicitPrefix[2];
        }
      }

      if (numVal === null || varName === null) {
        if (/([a-zA-Z0-9_.])\s+([a-zA-Z0-9_.])/.test(body)) {
          errors.push(`Línea ${lineNo}: falta un operador (+, -, *) entre términos en "${expr}".`);
          return null;
        }
        errors.push(`Línea ${lineNo}: término inválido "${match[0]}". Usa formato como "3*x1", "2x1", "1/2*x1" o "1e3*x1".`);
        return null;
      }
      const coefficient = (coeffsMap[varName] ?? 0) + sign * numVal;
      if (!Number.isFinite(coefficient)) {
        errors.push(`Línea ${lineNo}: coeficiente fuera del rango numérico en "${match[0]}".`);
        return null;
      }
      encountered.add(varName);
      coeffsMap[varName] = coefficient;
    }

    if (consumed !== normalized.length) {
      errors.push(`Línea ${lineNo}: no se pudo interpretar completamente "${expr}".`);
      return null;
    }

    return { coeffsMap, constant };
  };

  const extractObjectiveName = (headerPart: string): string => {
    const trimmed = headerPart.trim();
    const firstParen = trimmed.indexOf("(");
    const lastParen = trimmed.lastIndexOf(")");
    if (firstParen !== -1 && lastParen > firstParen) {
      return trimmed.slice(firstParen + 1, lastParen).trim();
    }
    return trimmed;
  };

  const parsedObjectives: { name: string; sense: ObjectiveSense; coeffsMap: Record<string, number> }[] = [];
  const parsedConstraints: { name: string; sense: ConstraintSense; rhs: number; coeffsMap: Record<string, number> }[] = [];
  let inConstraints = false;

  rawLines.forEach(({ line: rawLine, lineNo }) => {
    let line = rawLine;
    const saPrefix = line.match(/^(?:s\.a\.?|sujeto\s+a:?|restricciones:?)(?:\s+(.*))?$/i);
    if (saPrefix) {
      inConstraints = true;
      const remainder = (saPrefix[1] ?? "").trim();
      if (!remainder) return;
      line = remainder;
    }

    if (!inConstraints && /^(max|min|maximizar|minimizar)\b/i.test(line)) {
      const mObjNamed = line.match(/^(max|min|maximizar|minimizar)\s+(Z\d+\s*\(.*\))\s*=\s*(.+)$/i)
        ?? line.match(/^(max|min|maximizar|minimizar)\s+([^=]+?)\s*=\s*(.+)$/i);
      const mObjDirect = !mObjNamed ? line.match(/^(max|min|maximizar|minimizar)\s+(.+)$/i) : null;

      if (!mObjNamed && !mObjDirect) {
        errors.push(`Línea ${lineNo}: formato de objetivo inválido. Ejemplo: "Max Z1 = 1000*x1 + 3000*x2".`);
        return;
      }

      const rawSense = mObjNamed ? mObjNamed[1] : mObjDirect![1];
      const sense: ObjectiveSense = /^max/i.test(rawSense) ? "maximize" : "minimize";
      const extractedName = mObjNamed ? extractObjectiveName(mObjNamed[2]) : "";
      const namedIndex = mObjNamed?.[2].trim().match(/^Z(\d+)$/i);
      const original = existingModel.objectives[namedIndex ? Number(namedIndex[1]) - 1 : parsedObjectives.length];
      const name = (namedIndex ? original?.name ?? extractedName : extractedName || original?.name)
        || `Objetivo ${parsedObjectives.length + 1}`;
      const rhsExpr = mObjNamed ? mObjNamed[3] : mObjDirect![2];

      const parsedSide = parseLinearSide(rhsExpr, lineNo);
      if (parsedSide?.constant) {
        errors.push(`Línea ${lineNo}: los objetivos con término independiente requieren retirar esa constante.`);
      } else if (parsedSide) {
        parsedObjectives.push({ name, sense, coeffsMap: parsedSide.coeffsMap });
      }
      return;
    }

    // Restricción (soporta variables y constantes en ambos lados: lhs op rhs)
    inConstraints = true;
    const mCon = line.replace(/≤/g, "<=").replace(/≥/g, ">=").match(/^(.+?)\s*(<=|>=|==|=)\s*(.+)$/);
    if (!mCon) {
      errors.push(
        `Línea ${lineNo}: formato de restricción inválido ("${line}"). Ejemplo: "x1 + x2 <= 400" o "x1 <= 2*x2".`
      );
      return;
    }
    const lhsParsed = parseLinearSide(mCon[1].trim(), lineNo);
    const rhsParsed = parseLinearSide(mCon[3].trim(), lineNo);
    if (!lhsParsed || !rhsParsed) return;

    const rawSense = mCon[2];
    const sense: ConstraintSense = rawSense === "=" ? "==" : (rawSense as ConstraintSense);
    const netCoeffs: Record<string, number> = Object.assign(Object.create(null), lhsParsed.coeffsMap);
    for (const [v, val] of Object.entries(rhsParsed.coeffsMap)) {
      netCoeffs[v] = (netCoeffs[v] || 0) - val;
    }
    const netRhs = rhsParsed.constant - lhsParsed.constant;
    if (![netRhs, ...Object.values(netCoeffs)].every(Number.isFinite)) {
      errors.push(`Línea ${lineNo}: la restricción supera el rango numérico al agrupar términos.`);
      return;
    }
    const existingName = existingModel.constraints[parsedConstraints.length]?.name;
    parsedConstraints.push({
      name: existingName || `Restricción ${parsedConstraints.length + 1}`,
      sense,
      rhs: netRhs,
      coeffsMap: netCoeffs,
    });
  });

  if (parsedObjectives.length < 2 && errors.length === 0) {
    errors.push("Un problema multiobjetivo requiere al menos 2 funciones objetivo (Max/Min).");
  }

  const finalVars = [...existingTokens.filter(token => encountered.has(token)),
    ...Array.from(encountered).filter(token => !tokenToFullName.has(token))];
  if (finalVars.length < 1 && errors.length === 0) {
    errors.push("El modelo debe incluir al menos 1 variable de decisión en sus ecuaciones.");
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    detectedVariables: finalVars.map((tok) => tokenToFullName.get(tok) || tok),
    objectives: parsedObjectives.map((o) => ({
      name: o.name,
      sense: o.sense,
      coefficients: finalVars.map((v) => o.coeffsMap[v] || 0),
    })),
    constraints: parsedConstraints.map((c) => ({
      name: c.name,
      sense: c.sense,
      rhs: c.rhs,
      coefficients: finalVars.map((v) => c.coeffsMap[v] || 0),
    })),
    errors: [],
  };
}

/**
 * Genera el código LaTeX completo del modelo para vista previa matemática.
 */
export function modelToLatex(model: ModelDefinition): string {
  const varNames = model.variables.map((v) => v.name);
  const objLines = model.objectives.map((obj, idx) => {
    const sense = obj.sense === "maximize" ? "\\max" : "\\min";
    const expr = formatLinearExpr(obj.coefficients, varNames, true);
    return `${sense}\\; Z_{${idx + 1}} &= ${expr}`;
  });

  const conLines = model.constraints.map((c) => {
    const expr = formatLinearExpr(c.coefficients, varNames, true);
    const op = c.sense === "<=" ? "\\le" : c.sense === ">=" ? "\\ge" : "=";
    return `${expr} &${op} ${fmtLatexNum(c.rhs, null)}`;
  });

  const dupPrefixes = duplicateVarPrefixes(varNames);
  const domainLines = model.variables.map((v) => {
    const head = v.name.trim().split(/\s+/)[0];
    const vn = formatVarLatex(v.name, dupPrefixes.has(head));
    if (v.var_type === "binary") {
      const allowed = [0, 1].filter(x => x >= (v.lower_bound ?? 0) && x <= (v.upper_bound ?? 1));
      return allowed.length ? `${vn} \\in \\{${allowed.join(",")}\\}` : `${vn} \\in \\varnothing`;
    }
    const hasLb = v.lower_bound !== null && v.lower_bound !== undefined;
    const hasUb = v.upper_bound !== null && v.upper_bound !== undefined;
    const dom = v.var_type === "integer" ? ",\\;\\mathbb{Z}" : "";
    if (!hasLb && !hasUb) {
      return `${vn} \\in ${v.var_type === "integer" ? "\\mathbb{Z}" : "\\mathbb{R}"}`;
    }
    if (hasLb && !hasUb) return `${vn} \\ge ${fmtLatexNum(v.lower_bound, null)}${dom}`;
    if (!hasLb && hasUb) return `${vn} \\le ${fmtLatexNum(v.upper_bound, null)}${dom}`;
    return `${fmtLatexNum(v.lower_bound, null)} \\le ${vn} \\le ${fmtLatexNum(v.upper_bound, null)}${dom}`;
  });

  const domainRows: string[] = [];
  for (let i = 0; i < domainLines.length; i += 6) {
    const chunk = domainLines.slice(i, i + 6).join(",\\; ");
    domainRows.push(i === 0 ? `\\text{Dominio:}\\quad & ${chunk}` : `& ${chunk}`);
  }

  const parts = [
    "\\begin{aligned}",
    ...objLines.map((l) => `${l} \\\\`),
    ...(conLines.length > 0 ? ["\\text{s.a.}\\quad & \\\\", ...conLines.map((l) => `${l} \\\\`)] : []),
    ...domainRows.map((row, idx) => (idx < domainRows.length - 1 ? `${row} \\\\` : row)),
    "\\end{aligned}",
  ];
  return parts.join("\n");
}

/**
 * Genera las fórmulas LaTeX dinámicas para el Acordeón "Modo Rayos X (L_inf)".
 */
export function buildLinfXRayLatex(
  model: ModelDefinition,
  payoff: PayoffMatrixData,
  weights: number[],
  solLinf?: MetricSolution
): { headerLatex: string; constraintsLatex: string[]; lambdaVal: number | null } {
  const varNames = model.variables.map((v) => v.name);
  const headerLatex = `\\min\\; \\lambda \\quad \\text{sujeto a } \\lambda \\ge 0,\\; w_i \\cdot D_i(x) \\le \\lambda\\; \\forall i`;

  const constraintsLatex = model.objectives.map((obj, i) => {
    if (payoff.normalization_sources?.[i] === "constant") return String.raw`0 \le \lambda`;
    const w = weights[i] ?? 1 / model.objectives.length;
    const zIdeal = payoff.ideal_point[i] ?? 0;
    const zNadir = payoff.anti_ideal_point[i] ?? 0;
    const denom = payoff.normalization_ranges?.[i] || Math.abs(zIdeal - zNadir) || 1;
    const zExpr = formatLinearExpr(obj.coefficients, varNames, true);
    const zIdealStr = zIdeal < 0 ? `(${fmtLatexNum(zIdeal, 2)})` : fmtLatexNum(zIdeal, 2);
    const numLatex =
      obj.sense === "maximize"
        ? `${zIdealStr} - (${zExpr})`
        : `(${zExpr}) - ${zIdealStr}`;
    const dVal = solLinf?.normalized_distances?.[i];
    const wdVal = dVal !== undefined && Number.isFinite(dVal) ? w * dVal : null;
    const aggVal = solLinf?.aggregate_distance;
    const evalSuffix =
      wdVal !== null && Number.isFinite(wdVal) && aggVal !== undefined && Number.isFinite(aggVal)
        ? `\\quad \\Rightarrow \\; ${wdVal.toFixed(4)} \\le ${aggVal.toFixed(4)}`
        : "";
    return `${fmtLatexNum(w, 4)} \\cdot \\frac{${numLatex}}{${fmtLatexNum(denom, 2)}} \\le \\lambda ${evalSuffix}`;
  });

  return {
    headerLatex,
    constraintsLatex,
    lambdaVal:
      solLinf && Number.isFinite(solLinf.aggregate_distance) ? solLinf.aggregate_distance : null,
  };
}

function normalizedRow2D(constraint: ConstraintModel): [number, number, number] {
  const a = constraint.coefficients[0] ?? 0;
  const b = constraint.coefficients[1] ?? 0;
  const scale = Math.max(Math.abs(a), Math.abs(b));
  return scale && Number.isFinite(constraint.rhs / scale)
    ? [a / scale, b / scale, constraint.rhs / scale]
    : [a, b, constraint.rhs];
}

/**
 * Calcula el polígono convexo de la región factible en 2D (cuando n_vars === 2)
 * mediante intersección de semiplanos (Sutherland-Hodgman).
 */
export function computeFeasiblePolygon2D(
  model: ModelDefinition,
  payoff?: PayoffMatrixData,
): { x: number[]; y: number[] } | null {
  if (model.variables.length !== 2) return null;

  const [xBounds, yBounds] = model.variables.map((variable, idx) => {
    const rawLower = variable.var_type === "binary" ? Math.max(0, variable.lower_bound ?? 0) : variable.lower_bound;
    const rawUpper = variable.var_type === "binary" ? Math.min(1, variable.upper_bound ?? 1) : variable.upper_bound;
    const [lower, upper] = payoff?.decision_ranges_2d?.[idx] ?? [rawLower, rawUpper];
    const rawWitnesses = (payoff?.independent_solutions ?? [])
      .map((point) => point[variable.name])
      .filter(Number.isFinite);
    const constraintHints = !payoff?.decision_ranges_2d?.[idx]
      ? model.constraints
          .map((c) => {
            const coef = c.coefficients[idx] ?? 0;
            return Math.abs(coef) > 1e-12 && Number.isFinite(c.rhs) ? c.rhs / coef : NaN;
          })
          .filter(Number.isFinite)
      : [];
    const samples = [
      ...rawWitnesses,
      ...constraintHints,
      ...(lower !== null && lower !== undefined && Number.isFinite(lower) ? [lower] : []),
      ...(upper !== null && upper !== undefined && Number.isFinite(upper) ? [upper] : []),
    ];
    const safeSamples = samples.length > 0 ? samples : [0];
    const minWitness = Math.min(...safeSamples);
    const maxWitness = Math.max(...safeSamples);
    const pad = Math.max(1, maxWitness - minWitness) * 0.5;
    return [lower ?? minWitness - pad, upper ?? maxWitness + pad];
  });
  const [lb0, ub0] = xBounds;
  const [lb1, ub1] = yBounds;

  type Pt = [number, number];
  let poly: Pt[] = [
    [lb0, lb1],
    [ub0, lb1],
    [ub0, ub1],
    [lb0, ub1],
  ];

  // Recorta polígono por a*x + b*y <= rhs
  const clipHalfPlane = (pts: Pt[], a: number, b: number, rhs: number): Pt[] => {
    if (pts.length === 0) return [];
    const inside = (p: Pt) => a * p[0] + b * p[1] <= rhs + 1e-7;
    const intersect = (p1: Pt, p2: Pt): Pt => {
      const f1 = a * p1[0] + b * p1[1] - rhs;
      const f2 = a * p2[0] + b * p2[1] - rhs;
      const t = Math.abs(f1 - f2) > 1e-12 ? f1 / (f1 - f2) : 0.5;
      return [p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])];
    };

    const output: Pt[] = [];
    for (let i = 0; i < pts.length; i++) {
      const curr = pts[i];
      const prev = pts[(i + pts.length - 1) % pts.length];
      const currIn = inside(curr);
      const prevIn = inside(prev);
      if (currIn) {
        if (!prevIn) output.push(intersect(prev, curr));
        output.push(curr);
      } else if (prevIn) {
        output.push(intersect(prev, curr));
      }
    }
    return output;
  };

  for (const c of model.constraints) {
    const [a, b, rhs] = normalizedRow2D(c);
    if (c.sense === "<=") {
      poly = clipHalfPlane(poly, a, b, rhs);
    } else if (c.sense === ">=") {
      poly = clipHalfPlane(poly, -a, -b, -rhs);
    } else if (c.sense === "==") {
      poly = clipHalfPlane(poly, a, b, rhs);
      poly = clipHalfPlane(poly, -a, -b, -rhs);
    }
  }

  if (poly.length < 2) return null;
  const closed = [...poly, poly[0]];
  return {
    x: closed.map((p) => p[0]),
    y: closed.map((p) => p[1]),
  };
}

/**
 * Proyecta el polígono factible 2D del espacio de decisiones al espacio de objetivos (Z_x, Z_y)
 * mediante la envolvente convexa (Andrew's monotone chain) de los vértices transformados.
 */
export function computeFeasibleObjectivesPolygon2D(
  model: ModelDefinition,
  idxX: number,
  idxY: number,
  payoff?: PayoffMatrixData,
): { x: number[]; y: number[] } | null {
  if (model.variables.length !== 2) return null;
  const objX = model.objectives[idxX];
  const objY = model.objectives[idxY];
  if (!objX || !objY) return null;

  const decPoly = computeFeasiblePolygon2D(model, payoff);
  if (!decPoly || decPoly.x.length < 2) return null;

  const evalObj = (coeffs: number[], x0: number, x1: number) =>
    (coeffs[0] ?? 0) * x0 + (coeffs[1] ?? 0) * x1;

  const rawPtsAll: Array<[number, number]> = [];
  for (let i = 0; i < decPoly.x.length; i++) {
    rawPtsAll.push([
      evalObj(objX.coefficients, decPoly.x[i], decPoly.y[i]),
      evalObj(objY.coefficients, decPoly.x[i], decPoly.y[i]),
    ]);
  }
  const xsAll = rawPtsAll.map((p) => p[0]);
  const ysAll = rawPtsAll.map((p) => p[1]);
  const spanX = Math.max(1e-30, Math.max(...xsAll) - Math.min(...xsAll));
  const spanY = Math.max(1e-30, Math.max(...ysAll) - Math.min(...ysAll));

  const rawPts: Array<[number, number]> = [];
  for (const [zx, zy] of rawPtsAll) {
    if (!rawPts.some((p) => Math.hypot((p[0] - zx) / spanX, (p[1] - zy) / spanY) < 1e-6)) {
      rawPts.push([zx, zy]);
    }
  }

  if (rawPts.length < 2) return null;

  rawPts.sort((a, b) => (a[0] !== b[0] ? a[0] - b[0] : a[1] - b[1]));
  const cross = (o: [number, number], a: [number, number], b: [number, number]) =>
    (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const crossTol = 1e-9 * spanX * spanY;

  const lower: Array<[number, number]> = [];
  for (const p of rawPts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= crossTol) {
      lower.pop();
    }
    lower.push(p);
  }

  const upper: Array<[number, number]> = [];
  for (let i = rawPts.length - 1; i >= 0; i--) {
    const p = rawPts[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= crossTol) {
      upper.pop();
    }
    upper.push(p);
  }

  lower.pop();
  upper.pop();
  const hull = [...lower, ...upper];
  if (hull.length < 2) return null;

  const closed = [...hull, hull[0]];
  return {
    x: closed.map((p) => p[0]),
    y: closed.map((p) => p[1]),
  };
}

/**
 * Calcula curvas de isodistancia (L1 rombo, L2 elipse, L_inf rectángulo) en el espacio
 * de objetivos 2D centradas en el Punto Ideal Z* y pasando por cada solución compromiso.
 */
export function computeIsodistanceTraces2D(
  model: ModelDefinition,
  payoff: PayoffMatrixData,
  weights: number[],
  solutions: SolveResponse["solutions"],
  idxX: number,
  idxY: number,
  isDark = false
): Array<{ name: string; x: number[]; y: number[]; color: string; dash: string }> {
  const zIdX = payoff.ideal_point?.[idxX];
  const zIdY = payoff.ideal_point?.[idxY];
  const zNadX = payoff.anti_ideal_point?.[idxX];
  const zNadY = payoff.anti_ideal_point?.[idxY];

  const rX = payoff.normalization_ranges?.[idxX] || Math.abs(zIdX - zNadX) || 1;
  const rY = payoff.normalization_ranges?.[idxY] || Math.abs(zIdY - zNadY) || 1;
  const sX = model.objectives[idxX]?.sense === "maximize" ? -1 : 1;
  const sY = model.objectives[idxY]?.sense === "maximize" ? -1 : 1;

  const constX = payoff.normalization_sources?.[idxX] === "constant";
  const constY = payoff.normalization_sources?.[idxY] === "constant";
  const rawWX = weights[idxX] ?? 0;
  const rawWY = weights[idxY] ?? 0;
  if (![zIdX, zIdY, rX, rY, rawWX, rawWY].every(Number.isFinite) || rX <= 0 || rY <= 0) return [];
  const EPS_W = 1e-4;
  const wX = constX || rawWX <= EPS_W ? 0 : rawWX;
  const wY = constY || rawWY <= EPS_W ? 0 : rawWY;
  const l2Color = isDark ? "#CBD5E1" : "#334155";

  const traces: Array<{ name: string; x: number[]; y: number[]; color: string; dash: string }> = [];

  if (wX === 0 && wY === 0) return traces;
  if (wX === 0 || wY === 0) {
    if ((wX === 0 && constX) || (wY === 0 && constY)) {
      return traces;
    }
    // Los tres niveles fijan solo la desviación del eje con peso positivo.
    const span = Math.max(
      1,
      ...Object.values(solutions)
        .filter((sol): sol is MetricSolution => Boolean(sol && Array.isArray(sol.normalized_distances)))
        .map((sol) => sol.normalized_distances[wX === 0 ? idxX : idxY])
        .filter(Number.isFinite),
    );
    for (const [metric, name, color, dash] of [
      ["L1", "Iso L₁", "#2563EB", "dot"],
      ["L2", "Iso L₂", l2Color, "dash"],
      ["L_inf", "Iso L∞", "#E11D48", "dashdot"],
    ] as const) {
      const sol = solutions[metric];
      if (!sol || ![idxX, idxY].every(i => Number.isFinite(sol.normalized_distances?.[i]))) {
        continue;
      }
      const distances = sol.normalized_distances;
      const x = zIdX + sX * rX * distances[idxX];
      const y = zIdY + sY * rY * distances[idxY];
      traces.push({
        name, color, dash,
        x: wX === 0 ? [zIdX, zIdX + sX * rX * span] : [x, x],
        y: wY === 0 ? [zIdY, zIdY + sY * rY * span] : [y, y],
      });
    }
    return traces;
  }

  // L1: wX * dX + wY * dY = R1 (segmento diagonal del rombo dentro de la caja visible)
  const sol1 = solutions.L1;
  if (sol1?.normalized_distances && [idxX, idxY].every(i => Number.isFinite(sol1.normalized_distances[i]))) {
    const R1 = wX * sol1.normalized_distances[idxX] + wY * sol1.normalized_distances[idxY];
    if (R1 > 1e-6) {
      const dxMax = R1 / wX;
      const dyMax = R1 / wY;
      const pts: [number, number][] = [
        [zIdX + sX * dxMax * rX, zIdY],
        [zIdX, zIdY + sY * dyMax * rY],
      ];
      traces.push({
        name: "Iso L₁",
        x: pts.map((p) => p[0]),
        y: pts.map((p) => p[1]),
        color: "#2563EB",
        dash: "dot",
      });
    }
  }

  // L2: (wX * dX)^2 + (wY * dY)^2 = R2^2 (arco de elipse en el cuadrante factible)
  const sol2 = solutions.L2;
  if (sol2?.normalized_distances && [idxX, idxY].every(i => Number.isFinite(sol2.normalized_distances[i]))) {
    const R2sq =
      (wX * sol2.normalized_distances[idxX]) ** 2 + (wY * sol2.normalized_distances[idxY]) ** 2;
    if (R2sq > 1e-9) {
      const rx = Math.sqrt(R2sq) / wX;
      const ry = Math.sqrt(R2sq) / wY;
      const xs: number[] = [];
      const ys: number[] = [];
      const steps = 40;
      for (let k = 0; k <= steps; k++) {
        const theta = (Math.PI / 2) * (k / steps);
        const dx = rx * Math.cos(theta);
        const dy = ry * Math.sin(theta);
        xs.push(zIdX + sX * dx * rX);
        ys.push(zIdY + sY * dy * rY);
      }
      traces.push({
        name: "Iso L₂",
        x: xs,
        y: ys,
        color: l2Color,
        dash: "dash",
      });
    }
  }

  // L_inf: max(wX * dX, wY * dY) = lambda (esquina de cuadrado/rectángulo)
  const solInf = solutions.L_inf;
  if (solInf?.normalized_distances && [idxX, idxY].every(i => Number.isFinite(solInf.normalized_distances[i]))) {
    const lam = Math.max(
      wX * solInf.normalized_distances[idxX],
      wY * solInf.normalized_distances[idxY]
    );
    if (lam > 1e-6) {
      const dx = lam / wX;
      const dy = lam / wY;
      const cornerX = zIdX + sX * dx * rX;
      const cornerY = zIdY + sY * dy * rY;
      traces.push({
        name: "Iso L∞",
        x: [cornerX, cornerX, zIdX],
        y: [zIdY, cornerY, cornerY],
        color: "#E11D48",
        dash: "dashdot",
      });
    }
  }

  return traces;
}

const MODEL_COLUMNS = ["Seccion", "Nombre", "Tipo_o_Sentido", "Min_o_RHS", "Max_o_Peso"];
const RESERVED_MODEL_COLUMNS = new Set([
  ...MODEL_COLUMNS.map((name) => name.toLowerCase()), "sección", "tipo", "elemento",
  "name", "variable", "description", "descripcion", "pareto_seed", "referencia", "fuente",
  "var_type", "tipo_var", "min", "max", "lower_bound", "upper_bound", "lb", "ub",
  "sense", "sentido", "peso", "weight", "operador", "rhs", "ld", "__proto__",
]);

function coefficientColumn(name: string): string {
  return RESERVED_MODEL_COLUMNS.has(name.trim().toLowerCase()) || name.startsWith("Coef: ")
    ? `Coef: ${name}`
    : name;
}

/**
 * Calcula puntos discretos factibles en 2D cuando el modelo tiene variables enteras o binarias.
 * Si ambas variables son enteras/binarias y el rango es manejable, devuelve la malla de puntos factibles.
 */
export function computeDiscreteFeasiblePoints2D(
  model: ModelDefinition,
  payoff?: PayoffMatrixData,
): { x: number[]; y: number[] } | null {
  if (model.variables.length !== 2) return null;
  const v0 = model.variables[0];
  const v1 = model.variables[1];
  const isInt0 = v0.var_type === "integer" || v0.var_type === "binary";
  const isInt1 = v1.var_type === "integer" || v1.var_type === "binary";
  if (!isInt0 && !isInt1) return null;

  const poly = computeFeasiblePolygon2D(model, payoff);
  if (!poly || poly.x.length === 0) return null;

  const minX = Math.ceil(Math.min(...poly.x) - 1e-6);
  const maxX = Math.floor(Math.max(...poly.x) + 1e-6);
  const minY = Math.ceil(Math.min(...poly.y) - 1e-6);
  const maxY = Math.floor(Math.max(...poly.y) + 1e-6);
  if ((isInt0 && ![minX, maxX].every(Number.isSafeInteger)) ||
      (isInt1 && ![minY, maxY].every(Number.isSafeInteger))) return null;

  const rows = model.constraints.map((constraint) => ({
    sense: constraint.sense, values: normalizedRow2D(constraint),
  }));
  const satisfies = (px: number, py: number): boolean => {
    for (const { sense, values: [a, b, rhs] } of rows) {
      const lhs = a * px + b * py;
      if (sense === "<=" && lhs > rhs + 1e-6) return false;
      if (sense === ">=" && lhs < rhs - 1e-6) return false;
      if (sense === "==" && Math.abs(lhs - rhs) > 1e-6) return false;
    }
    if (v0.lower_bound !== null && px < v0.lower_bound - 1e-6) return false;
    if (v0.upper_bound !== null && px > v0.upper_bound + 1e-6) return false;
    if (v1.lower_bound !== null && py < v1.lower_bound - 1e-6) return false;
    if (v1.upper_bound !== null && py > v1.upper_bound + 1e-6) return false;
    return true;
  };

  const xs: number[] = [];
  const ys: number[] = [];

  if (isInt0 && isInt1) {
    const countX = Math.max(0, maxX - minX + 1);
    const countY = Math.max(0, maxY - minY + 1);
    if (countX * countY > 2500) return null;
    for (let ix = minX; ix <= maxX; ix++) {
      for (let iy = minY; iy <= maxY; iy++) {
        if (satisfies(ix, iy)) {
          xs.push(ix);
          ys.push(iy);
        }
      }
    }
  } else if (isInt0) {
    const countX = Math.max(0, maxX - minX + 1);
    if (countX > 80) return null;
    const minYCont = v1.lower_bound !== null ? Math.max(v1.lower_bound, Math.min(...poly.y)) : Math.min(...poly.y);
    const maxYCont = v1.upper_bound !== null ? Math.min(v1.upper_bound, Math.max(...poly.y)) : Math.max(...poly.y);
    for (let ix = minX; ix <= maxX; ix++) {
      let cMin = minYCont;
      let cMax = maxYCont;
      for (const { sense, values: [a, b, rhs] } of rows) {
        const rem = rhs - a * ix;
        if (Math.abs(b) <= 1e-12) {
          if (
            (sense === "<=" && 0 > rem + 1e-6) ||
            (sense === ">=" && 0 < rem - 1e-6) ||
            (sense === "==" && Math.abs(rem) > 1e-6)
          ) {
            cMax = -Infinity;
            break;
          }
          continue;
        }
        const bound = rem / b;
        if (sense === "==") {
          cMin = Math.max(cMin, bound);
          cMax = Math.min(cMax, bound);
        } else if ((sense === "<=" && b > 0) || (sense === ">=" && b < 0)) {
          cMax = Math.min(cMax, bound);
        } else {
          cMin = Math.max(cMin, bound);
        }
      }
      if (cMin <= cMax + 1e-7) {
        const lo = Math.min(cMin, cMax);
        const hi = Math.max(cMin, cMax);
        const steps = hi - lo < 1e-7 ? 0 : 12;
        for (let k = 0; k <= steps; k++) {
          const py = steps === 0 ? lo : lo + ((hi - lo) * k) / steps;
          if (satisfies(ix, py)) {
            xs.push(ix);
            ys.push(py);
          }
        }
      }
    }
  } else {
    const countY = Math.max(0, maxY - minY + 1);
    if (countY > 80) return null;
    const minXCont = v0.lower_bound !== null ? Math.max(v0.lower_bound, Math.min(...poly.x)) : Math.min(...poly.x);
    const maxXCont = v0.upper_bound !== null ? Math.min(v0.upper_bound, Math.max(...poly.x)) : Math.max(...poly.x);
    for (let iy = minY; iy <= maxY; iy++) {
      let cMin = minXCont;
      let cMax = maxXCont;
      for (const { sense, values: [a, b, rhs] } of rows) {
        const rem = rhs - b * iy;
        if (Math.abs(a) <= 1e-12) {
          if (
            (sense === "<=" && 0 > rem + 1e-6) ||
            (sense === ">=" && 0 < rem - 1e-6) ||
            (sense === "==" && Math.abs(rem) > 1e-6)
          ) {
            cMax = -Infinity;
            break;
          }
          continue;
        }
        const bound = rem / a;
        if (sense === "==") {
          cMin = Math.max(cMin, bound);
          cMax = Math.min(cMax, bound);
        } else if ((sense === "<=" && a > 0) || (sense === ">=" && a < 0)) {
          cMax = Math.min(cMax, bound);
        } else {
          cMin = Math.max(cMin, bound);
        }
      }
      if (cMin <= cMax + 1e-7) {
        const lo = Math.min(cMin, cMax);
        const hi = Math.max(cMin, cMax);
        const steps = hi - lo < 1e-7 ? 0 : 12;
        for (let k = 0; k <= steps; k++) {
          const px = steps === 0 ? lo : lo + ((hi - lo) * k) / steps;
          if (satisfies(px, iy)) {
            xs.push(px);
            ys.push(iy);
          }
        }
      }
    }
  }

  return xs.length > 0 ? { x: xs, y: ys } : null;
}

type TabularRow = Record<string, string | number | boolean | null | undefined>;

function tabularNumber(raw: unknown, field: string, fallback?: number): number {
  const value = typeof raw === "string" ? raw.trim().replace(",", ".") : raw;
  if ((value === "" || value == null) && fallback !== undefined) return fallback;
  if ((typeof value === "string" && value !== "") || typeof value === "number") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  throw new Error(`Ingresa un número válido en ${field}.`);
}

function parseBoundCell(raw: unknown, fallback: number | null, field: string): number | null {
  const value = String(raw ?? "").trim().toLowerCase();
  if (!value) return fallback;
  if (["-inf", "+inf", "inf", "-∞", "+∞", "∞"].includes(value)) return null;
  return tabularNumber(value, field);
}

function parseCsvRows(text: string): Array<Array<string>> {
  const rows: Array<Array<string>> = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  const clean = text.replace(/^\uFEFF/, "");

  for (let i = 0; i < clean.length; i++) {
    const ch = clean[i];
    if (inQuotes) {
      if (ch === '"') {
        if (clean[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\r" || ch === "\n") {
      if (ch === "\r" && clean[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += ch;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

function parseTabularMatrix(
  matrixRows: Array<Array<string | number | boolean | null>>,
  fileName: string,
): { model: ModelDefinition; weights: number[] } {
  if (matrixRows.length === 0) {
    throw new Error("La hoja importada está vacía.");
  }

  const headerIdx = matrixRows.findIndex(row =>
    row.some(cell => ["seccion", "sección"].includes(String(cell ?? "").trim().toLowerCase()))
  );
  if (headerIdx < 0) throw new Error("La hoja Modelo no contiene el encabezado Seccion de la plantilla.");

  const headerRow = matrixRows[headerIdx].map((h) => String(h ?? "").trim());
  const rows: TabularRow[] = matrixRows.slice(headerIdx + 1).map((r) => {
    const rec: TabularRow = Object.create(null);
    headerRow.forEach((colName, cIdx) => {
      if (colName) rec[colName] = r[cIdx];
    });
    return rec;
  });

  let importedName = fileName.replace(/\.(xlsx|csv|json)$/i, "");
  let importedSeed: number | undefined;
  let importedReference: string | undefined;
  let importedDescription = `Modelo importado desde ${fileName}.`;
  const variables: ModelDefinition["variables"] = [];
  const objRows: TabularRow[] = [];
  const conRows: TabularRow[] = [];

  const getField = (row: TabularRow, candidates: string[]) => {
    for (const candidate of candidates) {
      const key = Object.keys(row).find(k => k.toLowerCase() === candidate);
      if (key !== undefined) return row[key];
    }
    return undefined;
  };

  rows.forEach((row) => {
    const sec = String(getField(row, ["seccion", "sección", "tipo", "elemento"]) ?? "")
      .trim()
      .toLowerCase();
    if (sec === "meta" || sec === "metadata") {
      const metaName = String(getField(row, ["nombre", "name"]) ?? "").trim();
      const metaDesc = String(getField(row, ["tipo_o_sentido", "description", "descripcion"]) ?? "").trim();
      const seed = getField(row, ["min_o_rhs", "pareto_seed"]);
      if (seed !== undefined && seed !== "") importedSeed = Number(seed);
      if (metaName) importedName = metaName;
      if (metaDesc) importedDescription = metaDesc;
      importedReference = String(getField(row, ["referencia", "fuente", "max_o_peso"]) ?? "").trim() || undefined;
    } else if (sec.startsWith("var")) {
      const name = String(getField(row, ["nombre", "name", "variable"]) ?? "").trim();
      if (!name) throw new Error("Escribe el nombre de cada variable.");
      const vtRaw = String(getField(row, ["tipo_o_sentido", "var_type", "tipo_var"]) ?? "continuous")
        .trim()
        .toLowerCase();
      if (!["continuous", "continua", "integer", "entera", "binary", "binaria"].includes(vtRaw)) {
        throw new Error(`Tipo de variable desconocido en «${name}». Usa continuous, integer o binary.`);
      }
      const var_type =
        vtRaw.startsWith("int") || vtRaw.startsWith("ent")
          ? "integer"
          : vtRaw.startsWith("bin")
          ? "binary"
          : "continuous";
      const minRaw = getField(row, ["min_o_rhs", "min", "lower_bound", "lb"]);
      const maxRaw = getField(row, ["max_o_peso", "max", "upper_bound", "ub"]);
      variables.push({
        name,
        var_type,
        lower_bound: var_type === "binary" ? 0 : parseBoundCell(minRaw, 0, `cota inferior de «${name}»`),
        upper_bound: var_type === "binary" ? 1 : parseBoundCell(maxRaw, null, `cota superior de «${name}»`),
      });
    } else if (sec.startsWith("obj")) {
      objRows.push(row);
    } else if (sec.startsWith("res")) {
      conRows.push(row);
    } else if (sec) {
      throw new Error(`Sección desconocida «${sec}». Usa Meta, Variable, Objetivo o Restriccion.`);
    }
  });

  if (variables.length < 1 || objRows.length < 2) {
    throw new Error(
      "Diligencia la hoja Modelo con al menos una variable y dos objetivos."
    );
  }

  const varNames = variables.map((v) => v.name);
  const objectives: ModelDefinition["objectives"] = [];
  const importedWeights: Array<number | null> = [];
  const coefficientColumns = varNames.map((name) => {
    const encoded = coefficientColumn(name);
    // Los archivos antiguos conservan los nombres de columnas sin prefijo.
    const column = headerRow.includes(encoded) ? encoded : name;
    if (headerRow.filter(header => header === column).length !== 1 ||
        (column !== encoded && MODEL_COLUMNS.some(metadata => metadata.toLowerCase() === name.toLowerCase()))) {
      throw new Error(`La variable «${name}» necesita una columna de coeficientes inequívoca.`);
    }
    return column;
  });

  objRows.forEach((row, idx) => {
    const name = String(getField(row, ["nombre", "name"]) ?? `Objetivo ${idx + 1}`).trim();
    const sRaw = String(getField(row, ["tipo_o_sentido", "sense", "sentido"]) ?? "maximize")
      .trim()
      .toLowerCase();
    if (!name) throw new Error(`Escribe el nombre del objetivo ${idx + 1}.`);
    if (!["minimize", "minimizar", "min", "maximize", "maximizar", "max"].includes(sRaw)) {
      throw new Error(`Indica minimize o maximize en el objetivo «${name}».`);
    }
    const sense = sRaw.startsWith("min") ? "minimize" : "maximize";
    const coeffs = coefficientColumns.map((column, i) => tabularNumber(row[column], `«${name}», columna «${varNames[i]}»`, 0));
    objectives.push({ name, sense, coefficients: coeffs });
    const raw = getField(row, ["max_o_peso", "peso", "weight"]);
    importedWeights.push(String(raw ?? "").trim() ? tabularNumber(raw, `peso de «${name}»`) : null);
  });

  const constraints: ModelDefinition["constraints"] = conRows.map((row, idx) => {
    const name = String(getField(row, ["nombre", "name"]) ?? `Restricción ${idx + 1}`).trim();
    const sRaw = String(getField(row, ["tipo_o_sentido", "sense", "operador"]) ?? "<=").trim();
    if (!name) throw new Error(`Escribe el nombre de la restricción ${idx + 1} o elimina la fila.`);
    if (!["<=", "≤", ">=", "≥", "==", "="].includes(sRaw)) {
      throw new Error(`Usa <=, >= o = en la restricción «${name}».`);
    }
    const sense = sRaw === ">=" || sRaw === "≥" ? ">=" : sRaw === "==" || sRaw === "=" ? "==" : "<=";
    const rhsVal = tabularNumber(getField(row, ["min_o_rhs", "rhs", "ld"]), `lado derecho de «${name}»`);
    const coeffs = coefficientColumns.map((column, i) => tabularNumber(row[column], `«${name}», columna «${varNames[i]}»`, 0));
    return {
      name,
      coefficients: coeffs,
      sense,
      rhs: rhsVal,
    };
  });

  if (importedWeights.some(w => w === null) && importedWeights.some(w => w !== null)) {
    throw new Error("Completa todos los pesos o déjalos todos vacíos para usar pesos iguales.");
  }
  const normWeights = importedWeights.map(w => w ?? 1 / objectives.length);
  if (normWeights.some(w => w < 0 || w > 1) || Math.abs(normWeights.reduce((a, b) => a + b, 0) - 1) > 0.001 + 1e-12) {
    throw new Error("Los pesos deben estar entre 0 y 1 y sumar 1.");
  }

  return {
    model: {
      name: importedName,
      description: importedDescription,
      reference: importedReference,
      variables,
      objectives,
      constraints,
      weights: normWeights,
      pareto_seed: importedSeed,
    },
    weights: normWeights,
  };
}

function parseJsonModel(rawText: string, fileName: string): { model: ModelDefinition; weights: number[] } {
  let raw: unknown;
  try {
    raw = JSON.parse(rawText.replace(/^\uFEFF/, ""));
  } catch {
    throw new Error("El archivo JSON no tiene un formato válido.");
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("El archivo JSON debe contener un objeto con el modelo.");
  }
  const obj = raw as Record<string, unknown>;
  if (!Array.isArray(obj.variables) || obj.variables.length < 1 || !Array.isArray(obj.objectives) || obj.objectives.length < 2) {
    throw new Error("El modelo JSON debe incluir al menos 1 variable y 2 objetivos.");
  }
  const variables: ModelDefinition["variables"] = obj.variables.map((item, idx) => {
    if (!item || typeof item !== "object") throw new Error(`Variable #${idx + 1} inválida en el JSON.`);
    const v = item as Record<string, unknown>;
    const name = String(v.name ?? "").trim();
    if (!name) throw new Error(`Escribe el nombre de la variable #${idx + 1}.`);
    const var_type = (v.var_type === "integer" || v.var_type === "binary" ? v.var_type : "continuous") as ModelDefinition["variables"][number]["var_type"];
    const rawLb = v.lower_bound === undefined ? 0 : v.lower_bound;
    const rawUb = v.upper_bound === undefined ? null : v.upper_bound;
    const lb = var_type === "binary" ? 0 : rawLb === null ? null : tabularNumber(rawLb, `cota inferior de «${name}»`);
    const ub = var_type === "binary" ? 1 : rawUb === null ? null : tabularNumber(rawUb, `cota superior de «${name}»`);
    return { name, var_type, lower_bound: lb, upper_bound: ub };
  });

  const nVars = variables.length;
  const objectives: ModelDefinition["objectives"] = obj.objectives.map((item, idx) => {
    if (!item || typeof item !== "object") throw new Error(`Objetivo #${idx + 1} inválido en el JSON.`);
    const o = item as Record<string, unknown>;
    const name = String(o.name ?? `Objetivo ${idx + 1}`).trim();
    if (!name) throw new Error(`Escribe el nombre del objetivo #${idx + 1}.`);
    const sense = o.sense === "minimize" ? "minimize" : "maximize";
    const coeffsRaw = Array.isArray(o.coefficients) ? o.coefficients : [];
    const coefficients = Array.from({ length: nVars }, (_, j) => tabularNumber(coeffsRaw[j] ?? 0, `«${name}», variable #${j + 1}`, 0));
    return { name, sense, coefficients };
  });

  const constraintsRaw = Array.isArray(obj.constraints) ? obj.constraints : [];
  const constraints: ModelDefinition["constraints"] = constraintsRaw.map((item, idx) => {
    if (!item || typeof item !== "object") throw new Error(`Restricción #${idx + 1} inválida en el JSON.`);
    const c = item as Record<string, unknown>;
    const name = String(c.name ?? `Restricción ${idx + 1}`).trim() || `Restricción ${idx + 1}`;
    const sense = c.sense === ">=" || c.sense === "==" ? c.sense : "<=";
    const rhs = tabularNumber(c.rhs, `lado derecho de «${name}»`);
    const coeffsRaw = Array.isArray(c.coefficients) ? c.coefficients : [];
    const coefficients = Array.from({ length: nVars }, (_, j) => tabularNumber(coeffsRaw[j] ?? 0, `«${name}», variable #${j + 1}`, 0));
    return { name, sense, rhs, coefficients };
  });

  let normWeights: number[];
  if (Array.isArray(obj.weights) && obj.weights.length === objectives.length) {
    normWeights = obj.weights.map((w, i) => tabularNumber(w, `peso de «${objectives[i].name}»`));
    if (normWeights.some(w => w < 0 || w > 1) || Math.abs(normWeights.reduce((a, b) => a + b, 0) - 1) > 0.001 + 1e-12) {
      throw new Error("Los pesos deben estar entre 0 y 1 y sumar 1.");
    }
  } else {
    normWeights = Array<number>(objectives.length).fill(1 / objectives.length);
  }

  return {
    model: {
      name: String(obj.name ?? fileName.replace(/\.json$/i, "")).trim() || "Modelo importado",
      description: typeof obj.description === "string" ? obj.description : "",
      reference: typeof obj.reference === "string" ? obj.reference : undefined,
      variables,
      objectives,
      constraints,
      weights: normWeights,
      pareto_seed: typeof obj.pareto_seed === "number" && Number.isInteger(obj.pareto_seed) ? obj.pareto_seed : undefined,
    },
    weights: normWeights,
  };
}

/** Lee un modelo desde Excel (.xlsx), JSON (.json) o CSV (.csv). */
export async function importModelFromFile(file: File): Promise<{ model: ModelDefinition; weights: number[] }> {
  const lower = file.name.toLowerCase();
  if (lower.endsWith(".json")) {
    return parseJsonModel(await file.text(), file.name);
  }
  if (lower.endsWith(".csv")) {
    return parseTabularMatrix(parseCsvRows(await file.text()), file.name);
  }
  if (!lower.endsWith(".xlsx")) {
    throw new Error("Selecciona un archivo .xlsx, .json o .csv con el modelo.");
  }
  const buf = await file.arrayBuffer();
  const bytes = new Uint8Array(buf);
  if (bytes[0] !== 0x50 || bytes[1] !== 0x4b) {
    throw new Error("El archivo no es un libro Excel (.xlsx) válido.");
  }
  let wb: import("xlsx").WorkBook;
  const xlsxMod = await import("xlsx");
  const XLSX = xlsxMod.default ?? xlsxMod;
  try {
    wb = XLSX.read(buf, { type: "array" });
  } catch {
    throw new Error("No se pudo leer el libro Excel. Guarda el ejercicio como .xlsx y vuelve a cargarlo.");
  }
  const sheetName = wb.SheetNames.find(name => name.toLowerCase() === "modelo");
  if (!sheetName) throw new Error("Falta la hoja «Modelo». Usa la plantilla oficial de OptiCompromise.");

  const sheet = wb.Sheets[sheetName];
  const matrixRows = XLSX.utils.sheet_to_json<Array<string | number | boolean | null>>(sheet, {
    header: 1,
    defval: "",
  });
  return parseTabularMatrix(matrixRows, file.name);
}
