import assert from "node:assert/strict";
import { test } from "node:test";
import { availableWeight, changeWeight, createWeights, equalizeWeights, remapWeights } from "../components/cockpit/weights.ts";

function accept(change) {
  assert.ok("state" in change, change.error);
  assert.ok(change.state.values.every(value => value >= 0 && value <= 1));
  assert.ok(Math.abs(change.state.values.reduce((sum, value) => sum + value, 0) - 1) < 1e-12);
  return change.state;
}

test("fijar los pesos permite escribir 0.5, 0.1 y 0.4", () => {
  let state = createWeights([1 / 3, 1 / 3, 1 / 3]);
  state = accept(changeWeight(state, 0, 0.5));
  state.fixed[0] = true;
  state = accept(changeWeight(state, 1, 0.1));
  assert.deepEqual(state.values, [0.5, 0.1, 0.4]);
  state.fixed[1] = true;
  assert.match(changeWeight(state, 2, 0.2).error, /único peso libre/);
  state.fixed[1] = false;
  assert.equal(accept(changeWeight(state, 2, 0.35)).values[0], 0.5);
});

test("un peso fijo conserva todos sus decimales y los libres se redistribuyen proporcionalmente", () => {
  const fixedValue = 0.1254321987;
  const state = { values: [fixedValue, 0.3, 0.1, 0.6 - fixedValue], fixed: [true, false, false, false] };
  const next = accept(changeWeight(state, 3, 0.17));
  assert.equal(next.values[0], fixedValue);
  assert.equal(next.values[3], 0.17);
  assert.ok(Math.abs(next.values[1] / next.values[2] - 3) < 1e-12);
});

test("rechaza pesos inválidos o que exceden el saldo sin cambiar el estado", () => {
  const state = { values: [0.6, 0.4, 0], fixed: [true, false, false] };
  for (const invalid of [NaN, -0.1, 1.01, Infinity]) assert.match(changeWeight(state, 1, invalid).error, /entre 0 y 1/);
  assert.match(changeWeight(state, 1, 0.5).error, /disponible/);
  assert.deepEqual(state.values, [0.6, 0.4, 0]);
  assert.match(changeWeight(state, 0, 0.5).error, /Desbloquea/);
});

test("tolera pesos cero y reparte por igual cuando todos los otros libres estaban en cero", () => {
  const state = { values: [1, 0, 0, 0], fixed: [false, true, false, false] };
  const next = accept(changeWeight(state, 0, 0));
  assert.deepEqual(next.values, [0, 0, 0.5, 0.5]);
  const pinnedTotal = { values: [1, 0, 0], fixed: [true, false, false] };
  assert.equal(availableWeight(pinnedTotal), 0);
  assert.match(changeWeight(pinnedTotal, 1, 0.1).error, /disponible/);
});

test("igualar conserva los pines compatibles y pide desbloquear los demás", () => {
  const state = { values: [0.5, 0.1, 0.4], fixed: [true, true, true] };
  assert.match(equalizeWeights(state).error, /desbloquea/);
  const equal = { values: [0.5, 0.5], fixed: [true, true] };
  assert.deepEqual(accept(equalizeWeights(equal)), equal);
  const compatible = { values: [0.25, 0.25, 0.4, 0.1], fixed: [true, true, false, false] };
  assert.deepEqual(accept(equalizeWeights(compatible)), { values: [0.25, 0.25, 0.25, 0.25], fixed: compatible.fixed });
});

test("agregar, eliminar o reordenar objetivos conserva los pines de los objetivos que permanecen", () => {
  const state = { values: [0.5, 0.1, 0.4], fixed: [true, false, true] };
  const next = accept(remapWeights(state, [2, 0, 1, -1]));
  assert.equal(next.values[0], 0.4);
  assert.equal(next.values[1], 0.5);
  assert.deepEqual(next.fixed, [true, true, false, false]);
  assert.match(remapWeights(state, [2, 0]).error, /Desbloquea/);
  const removed = accept(remapWeights(state, [0, 1]));
  assert.deepEqual(removed, { values: [0.5, 0.5], fixed: [true, false] });
});

test("cargar un ejercicio nuevo limpia los pines y ajusta redondeos en el archivo", () => {
  const next = createWeights([0.3333, 0.3333, 0.3333]);
  assert.deepEqual(next.values, [1 / 3, 1 / 3, 1 / 3]);
  assert.deepEqual(next.fixed, [false, false, false]);
});
