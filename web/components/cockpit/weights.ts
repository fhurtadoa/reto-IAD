const EPSILON = 1e-12;

export type WeightState = { values: number[]; fixed: boolean[] };
type WeightChange = { state: WeightState } | { error: string };

export function createWeights(values: number[]): WeightState {
  const sum = values.reduce((total, value) => total + value, 0);
  return {
    values: Math.abs(sum - 1) <= EPSILON ? values : values.map(value => value / sum),
    fixed: values.map(() => false),
  };
}

export function availableWeight({ values, fixed }: WeightState): number {
  return Math.max(0, 1 - values.reduce((sum, value, index) => fixed[index] ? sum + value : sum, 0));
}

function redistribute(values: number[], indices: number[], total: number) {
  const previousTotal = indices.reduce((sum, index) => sum + values[index], 0);
  let assigned = 0;
  // Put the floating-point remainder in the largest share to keep zeros at zero.
  const remainderIndex = indices.reduce((largest, index) => values[index] > values[largest] ? index : largest);
  for (const index of indices) {
    if (index === remainderIndex) continue;
    values[index] = previousTotal > 0 ? total * (values[index] / previousTotal) : total / indices.length;
    assigned += values[index];
  }
  values[remainderIndex] = Math.max(0, total - assigned);
}

export function changeWeight(state: WeightState, index: number, value: number): WeightChange {
  if (state.fixed[index]) return { error: "Desbloquea el peso para ajustarlo." };
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    return { error: "Escribe un peso válido entre 0 y 1." };
  }

  const maximum = availableWeight(state);
  if (state.values[index] === value) return { state };
  if (value > maximum + EPSILON) {
    return { error: "Ese peso supera lo que queda disponible. Reduce el valor o desbloquea algún peso." };
  }

  const others = state.values.map((_, i) => i).filter(i => i !== index && !state.fixed[i]);
  if (!others.length) {
    return { error: "El único peso libre toma el valor que falta para sumar 1. Desbloquea otro peso para ajustarlo." };
  }
  const values = [...state.values];
  values[index] = value;
  redistribute(values, others, Math.max(0, maximum - value));
  return { state: { ...state, values } };
}

export function equalizeWeights(state: WeightState): WeightChange {
  const equal = 1 / state.values.length;
  if (state.fixed.some((fixed, index) => fixed && Math.abs(state.values[index] - equal) > EPSILON)) {
    return { error: "Para igualar todos los pesos, desbloquea los que ya tienen un valor distinto." };
  }
  const values = state.values.map((value, index) => state.fixed[index] ? value : equal);
  return { state: { ...state, values } };
}

export function remapWeights(state: WeightState, indices: number[]): WeightChange {
  const values = indices.map(index => state.values[index] ?? 1 / indices.length);
  const fixed = indices.map(index => state.fixed[index] ?? false);
  const free = indices.map((_, i) => i).filter(i => !fixed[i]);
  const available = availableWeight({ values, fixed });
  if (!free.length && available > EPSILON) {
    return { error: "Desbloquea un peso de los objetivos que vas a conservar antes de aplicar este cambio." };
  }
  if (free.length) redistribute(values, free, available);
  return { state: { values, fixed } };
}
