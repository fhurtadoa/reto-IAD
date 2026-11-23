export type VarType = "continuous" | "integer" | "binary";
export type ObjectiveSense = "maximize" | "minimize";
export type ConstraintSense = "<=" | ">=" | "==";

export interface VariableModel {
  name: string;
  var_type: VarType;
  lower_bound: number | null;
  upper_bound: number | null;
}

export interface ObjectiveModel {
  name: string;
  sense: ObjectiveSense;
  coefficients: number[];
  expression?: string | null;
}

export interface ConstraintModel {
  name: string;
  coefficients: number[];
  sense: ConstraintSense;
  rhs: number;
  expression?: string | null;
}

export interface ModelDefinition {
  name: string;
  description?: string;
  reference?: string | null;
  variables: VariableModel[];
  objectives: ObjectiveModel[];
  constraints: ConstraintModel[];
  weights?: number[];
  pareto_seed?: number;
}

export interface PayoffMatrixData {
  headers: string[];
  matrix: number[][];
  ideal_point: number[];
  anti_ideal_point: number[];
  independent_solutions: Record<string, number>[];
  degenerate_objectives?: number[];
  normalization_ranges?: number[];
  normalization_sources?: Array<"payoff" | "feasible_range" | "constant" | "unit">;
  decision_ranges_2d?: Array<[number | null, number | null]> | null;
  status: string;
}

export interface MetricSolution {
  metric: string;
  variables: Record<string, number>;
  objectives: number[];
  achievement_pct: number[];
  normalized_distances: number[];
  aggregate_distance: number;
  status: string;
}

export interface ParetoPoint {
  weights: number[];
  objectives: number[];
  variables: Record<string, number>;
  metric: string;
  status?: string;
}

export interface SensitivityPoint {
  w1: number;
  weights: number[];
  deviations_pct: number[];
  objectives: number[];
  status: string;
}

export interface WeightSensitivityData {
  objective_index: number;
  objective_name: string;
  objective_names: string[];
  l1: SensitivityPoint[];
  l2: SensitivityPoint[];
  l_inf: SensitivityPoint[];
}

export interface SolveResponse {
  status: string;
  message: string;
  payoff: PayoffMatrixData;
  solutions: {
    L1: MetricSolution;
    L2: MetricSolution;
    L_inf: MetricSolution;
    [key: string]: MetricSolution;
  };
  weights: number[];
  pareto_points?: ParetoPoint[];
  weight_sensitivity?: WeightSensitivityData | null;
}

export type SolverStatus = "idle" | "calculating" | "partial" | "optimal" | "infeasible" | "unbounded" | "error";

export type ThemeMode = "dark" | "light";

export const BLANK_MODEL: ModelDefinition = {
  name: "Nuevo Modelo Multiobjetivo",
  description: "Modelo editable desde cero para formular variables, objetivos y restricciones.",
  variables: [
    { name: "x1 (Alternativa A)", var_type: "continuous", lower_bound: 0, upper_bound: 100 },
    { name: "x2 (Alternativa B)", var_type: "continuous", lower_bound: 0, upper_bound: 100 },
  ],
  objectives: [
    { name: "Objetivo 1", sense: "maximize", coefficients: [2, 3] },
    { name: "Objetivo 2", sense: "minimize", coefficients: [1, 1] },
  ],
  constraints: [
    { name: "Restricción 1", coefficients: [1, 1], sense: "<=", rhs: 50 },
    { name: "Restricción 2", coefficients: [2, 1], sense: ">=", rhs: 20 },
  ],
  weights: [0.5, 0.5],
};

export const FALLBACK_CELDAS_MODEL: ModelDefinition = {
  name: "Planificación de Celdas Fotovoltaicas (Clase 15)",
  description: "Problema biobjetivo del curso: maximizar utilidad económica vs minimizar generación de contaminantes.",
  reference: "IAD · Clase 11 y Clase 15 (Programación de Compromiso), caso Celdas Fotovoltaicas — Prof. Patricia Jaramillo Álvarez, UNAL.",
  variables: [
    { name: "x1 (Celdas Fotov.)", var_type: "continuous", lower_bound: 0, upper_bound: 300 },
    { name: "x2 (Celdas GP)", var_type: "continuous", lower_bound: 0, upper_bound: 200 },
  ],
  objectives: [
    { name: "Utilidad Total (USD)", sense: "maximize", coefficients: [1000, 3000] },
    { name: "Emisión Contaminantes (kg)", sense: "minimize", coefficients: [1, 2] },
  ],
  constraints: [
    { name: "Capacidad Máxima de Ensamble", coefficients: [1, 1], sense: "<=", rhs: 400 },
    { name: "Demanda Mínima de Ingreso", coefficients: [1000, 3000], sense: ">=", rhs: 300000 },
  ],
  weights: [0.5, 0.5],
};

export const SEMANTIC_COLORS = {
  ideal: "#D97706",    // Dorado / Amber
  nadir: "#BE123C",    // Rojo oscuro / Nadir
  L1: "#2563EB",       // Azul Cobalto
  L2: "#334155",       // Slate / Marino Técnico
  L_inf: "#E11D48",    // Rojo Suizo / Minimax
  pareto: "#0F766E",   // Verde petróleo / Pareto (o azul acero)
};
