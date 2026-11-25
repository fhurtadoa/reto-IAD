const assert = require("node:assert/strict");
const { readdirSync, readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const ts = require("typescript");
const xlsx = require("xlsx");

if (!require.extensions[".ts"]) {
  require.extensions[".ts"] = (module, filename) => {
    const { outputText } = ts.transpileModule(readFileSync(filename, "utf8"), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    });
    module._compile(outputText, filename);
  };
}

const { importModelFromFile } = require("../components/cockpit/mathUtils.ts");

const ROOT_DIR = path.resolve(__dirname, "..", "..");
const EXAMPLES_DIR = path.join(ROOT_DIR, "examples");
const EXERCISES_DIR = path.join(ROOT_DIR, "ejercicios");
const TEMPLATE_PATH = path.join(ROOT_DIR, "web", "public", "plantilla-ejercicio-iad.xlsx");

function fileFromBuffer(buffer, name) {
  return new File([buffer], name);
}

test("los 6 ejercicios .xlsx de ejercicios/ se importan fielmente frente a examples/*.json", async () => {
  const jsonFiles = readdirSync(EXAMPLES_DIR).filter((f) => f.endsWith(".json")).sort();
  assert.equal(jsonFiles.length, 6);

  for (const jsonName of jsonFiles) {
    const expected = JSON.parse(readFileSync(path.join(EXAMPLES_DIR, jsonName), "utf8").replace(/^\uFEFF/, ""));
    const xlsxName = jsonName.replace(/\.json$/i, ".xlsx");
    const xlsxBuf = readFileSync(path.join(EXERCISES_DIR, xlsxName));
    const imported = await importModelFromFile(fileFromBuffer(xlsxBuf, xlsxName));

    assert.equal(imported.model.name, expected.name, `${xlsxName}: nombre`);
    assert.equal(imported.model.description, expected.description, `${xlsxName}: descripcion`);
    assert.equal(imported.model.reference ?? undefined, expected.reference ?? undefined, `${xlsxName}: referencia`);
    assert.equal(imported.model.pareto_seed ?? 42, expected.pareto_seed ?? 42, `${xlsxName}: semilla`);

    assert.equal(imported.model.variables.length, expected.variables.length, `${xlsxName}: # variables`);
    imported.model.variables.forEach((v, idx) => {
      const ev = expected.variables[idx];
      assert.equal(v.name, ev.name, `${xlsxName}: var ${idx} nombre`);
      assert.equal(v.var_type, ev.var_type, `${xlsxName}: var ${idx} tipo`);
      assert.equal(v.lower_bound, ev.lower_bound ?? 0, `${xlsxName}: var ${idx} lb`);
      assert.equal(v.upper_bound, ev.upper_bound ?? null, `${xlsxName}: var ${idx} ub`);
    });

    assert.equal(imported.model.objectives.length, expected.objectives.length, `${xlsxName}: # objetivos`);
    imported.model.objectives.forEach((o, idx) => {
      const eo = expected.objectives[idx];
      assert.equal(o.name, eo.name, `${xlsxName}: obj ${idx} nombre`);
      assert.equal(o.sense, eo.sense, `${xlsxName}: obj ${idx} sentido`);
      o.coefficients.forEach((c, cIdx) => {
        assert.ok(Math.abs(c - eo.coefficients[cIdx]) <= 1e-9, `${xlsxName}: obj ${idx} coef ${cIdx}`);
      });
    });

    assert.equal(imported.model.constraints.length, expected.constraints.length, `${xlsxName}: # restricciones`);
    imported.model.constraints.forEach((con, idx) => {
      const econ = expected.constraints[idx];
      assert.equal(con.name, econ.name, `${xlsxName}: con ${idx} nombre`);
      assert.equal(con.sense, econ.sense, `${xlsxName}: con ${idx} sentido`);
      assert.ok(Math.abs(con.rhs - econ.rhs) <= 1e-9, `${xlsxName}: con ${idx} rhs`);
      con.coefficients.forEach((c, cIdx) => {
        assert.ok(Math.abs(c - econ.coefficients[cIdx]) <= 1e-9, `${xlsxName}: con ${idx} coef ${cIdx}`);
      });
    });

    const expectedWeights = expected.weights ?? Array(expected.objectives.length).fill(1 / expected.objectives.length);
    imported.weights.forEach((w, idx) => {
      assert.ok(Math.abs(w - expectedWeights[idx]) <= 1e-6, `${xlsxName}: peso ${idx}`);
    });
  }
});

test("plantilla-ejercicio-iad.xlsx rechaza hoja en blanco y su hoja Ejemplo_Papel es importable", async () => {
  const buf = readFileSync(TEMPLATE_PATH);
  await assert.rejects(
    () => importModelFromFile(fileFromBuffer(buf, "plantilla-ejercicio-iad.xlsx")),
    /Escribe el nombre del objetivo/
  );

  // Copiar Ejemplo_Papel como hoja Modelo verifica compatibilidad de la referencia incluida
  const wb = xlsx.read(buf, { type: "buffer" });
  const copyWb = xlsx.utils.book_new();
  xlsx.utils.book_append_sheet(copyWb, wb.Sheets["Ejemplo_Papel"], "Modelo");
  const out = xlsx.write(copyWb, { type: "buffer", bookType: "xlsx" });
  const parsed = await importModelFromFile(fileFromBuffer(out, "papel_desde_plantilla.xlsx"));
  assert.equal(parsed.model.variables.length, 12);
  assert.equal(parsed.model.objectives.length, 2);
  assert.equal(parsed.model.constraints.length, 7);
});

test("importador Excel y CSV soporta comas decimales, operadores Unicode, columnas reservadas y pesos vacios", async () => {
  const ws = xlsx.utils.aoa_to_sheet([
    ["Banner", "Test"],
    ["Seccion", "Nombre", "Tipo_o_Sentido", "Min_o_RHS", "Max_o_Peso", "Coef: Seccion", "Coef: Max", "x_int"],
    ["Meta", "Caso Decimal & Reservado", "Enunciado con coma", 77, "Fuente UNAL"],
    ["Variable", "Seccion", "binaria", -5, 9],
    ["Variable", "Max", "continuous", "-∞", "+inf"],
    ["Variable", "x_int", "entera", "", 10],
    ["Objetivo", "Utilidad", "max", "", "", "1,5", "-2,25", 3],
    ["Objetivo", "Impacto", "minimizar", "", "", 4, 0, "0,5"],
    ["Restriccion", "Igualdad", "=", "12,5", "", 1, 1, 0],
    ["Restriccion", "Tope", "≥", 2, "", 0, 1, 1],
  ]);
  const wb = xlsx.utils.book_new();
  xlsx.utils.book_append_sheet(wb, ws, "Modelo");
  const xlsxBuf = xlsx.write(wb, { type: "buffer", bookType: "xlsx" });

  const fromXlsx = await importModelFromFile(fileFromBuffer(xlsxBuf, "adversarial.xlsx"));
  assert.equal(fromXlsx.model.name, "Caso Decimal & Reservado");
  assert.equal(fromXlsx.model.pareto_seed, 77);
  assert.equal(fromXlsx.model.reference, "Fuente UNAL");
  assert.deepEqual(fromXlsx.model.variables, [
    { name: "Seccion", var_type: "binary", lower_bound: 0, upper_bound: 1 },
    { name: "Max", var_type: "continuous", lower_bound: null, upper_bound: null },
    { name: "x_int", var_type: "integer", lower_bound: 0, upper_bound: 10 },
  ]);
  assert.deepEqual(fromXlsx.model.objectives.map((o) => [o.sense, o.coefficients]), [
    ["maximize", [1.5, -2.25, 3]],
    ["minimize", [4, 0, 0.5]],
  ]);
  assert.deepEqual(fromXlsx.model.constraints.map((c) => [c.sense, c.rhs, c.coefficients]), [
    ["==", 12.5, [1, 1, 0]],
    [">=", 2, [0, 1, 1]],
  ]);
  assert.deepEqual(fromXlsx.weights, [0.5, 0.5]);

  const csvText = [
    "\uFEFFSeccion,Nombre,Tipo_o_Sentido,Min_o_RHS,Max_o_Peso,x1,x2",
    'Meta,"Modelo CSV, prueba",Desc,15,Ref',
    "Variable,x1,continua,0,100",
    "Variable,x2,integer,1,20",
    "Objetivo,Z1,maximize,,0.4,10,20",
    "Objetivo,Z2,minimize,,0.6,2,1",
    'Restriccion,"Capacidad, planta",<=,50,,1,2',
  ].join("\r\n");
  const fromCsv = await importModelFromFile(fileFromBuffer(Buffer.from(csvText, "utf8"), "modelo.csv"));
  assert.equal(fromCsv.model.name, "Modelo CSV, prueba");
  assert.equal(fromCsv.model.pareto_seed, 15);
  assert.deepEqual(fromCsv.weights, [0.4, 0.6]);
  assert.equal(fromCsv.model.constraints[0].name, "Capacidad, planta");
});

test("importador rechaza pesos inconsistentes, columnas ambiguas o archivos corruptos", async () => {
  await assert.rejects(
    () => importModelFromFile(fileFromBuffer(Buffer.from("not a zip"), "roto.xlsx")),
    /no es un libro Excel/
  );
  await assert.rejects(
    () => importModelFromFile(fileFromBuffer(Buffer.from("texto"), "modelo.txt")),
    /\.xlsx, \.json o \.csv/
  );

  const mixedWeightsCsv = [
    "Seccion,Nombre,Tipo_o_Sentido,Min_o_RHS,Max_o_Peso,x1",
    "Variable,x1,continuous,0,10",
    "Objetivo,Z1,maximize,,0.5,1",
    "Objetivo,Z2,minimize,,,2",
  ].join("\n");
  await assert.rejects(
    () => importModelFromFile(fileFromBuffer(Buffer.from(mixedWeightsCsv), "pesos.csv")),
    /Completa todos los pesos/
  );

  const reservedAmbiguousCsv = [
    "Seccion,Nombre,Tipo_o_Sentido,Min_o_RHS,Max_o_Peso",
    "Variable,Max,continuous,0,10",
    "Objetivo,Z1,maximize,,0.5",
    "Objetivo,Z2,minimize,,0.5",
  ].join("\n");
  await assert.rejects(
    () => importModelFromFile(fileFromBuffer(Buffer.from(reservedAmbiguousCsv), "reservada.csv")),
    /columna de coeficientes inequívoca/
  );
});

test("CSV con punto y coma (;), fórmulas sin caché en Excel y validación estricta de JSON", async () => {
  const semicolonCsv = [
    "Seccion;Nombre;Tipo_o_Sentido;Min_o_RHS;Max_o_Peso;x1;x2",
    'Meta;"Modelo; Español";Desc;;Ref UNAL',
    "Variable;x1;continua;0;100",
    "Variable;x2;entera;1;20",
    "Objetivo;Z1;max;;0,4;10,5;20",
    "Objetivo;Z2;min;;0,6;1;2,5",
    "Restriccion;Balance;=;12,5;;1;1",
  ].join("\r\n");
  const fromSemi = await importModelFromFile(fileFromBuffer(Buffer.from(semicolonCsv, "utf8"), "espanol.csv"));
  assert.equal(fromSemi.model.name, "Modelo; Español");
  assert.deepEqual(fromSemi.model.objectives.map((o) => [o.sense, o.coefficients]), [
    ["maximize", [10.5, 20]],
    ["minimize", [1, 2.5]],
  ]);
  assert.equal(fromSemi.model.constraints[0].sense, "==");
  assert.equal(fromSemi.model.constraints[0].rhs, 12.5);
  assert.deepEqual(fromSemi.weights, [0.4, 0.6]);

  const wsUncached = xlsx.utils.aoa_to_sheet([
    ["Seccion", "Nombre", "Tipo_o_Sentido", "Min_o_RHS", "Max_o_Peso", "x1", "x2"],
    ["Variable", "x1", "continuous", 0, 10],
    ["Variable", "x2", "continuous", 0, 10],
    ["Objetivo", "Z1", "maximize", "", 0.5, 2, 3],
    ["Objetivo", "Z2", "minimize", "", 0.5, 1, 1],
    ["Restriccion", "R1", "<=", 5, "", { t: "n", f: "1/53" }, 1],
  ]);
  const wbUncached = xlsx.utils.book_new();
  xlsx.utils.book_append_sheet(wbUncached, wsUncached, "Modelo");
  await assert.rejects(
    () => importModelFromFile(fileFromBuffer(xlsx.write(wbUncached, { type: "buffer", bookType: "xlsx" }), "uncached.xlsx")),
    /fórmula sin valor calculado/
  );

  const wsCached = xlsx.utils.aoa_to_sheet([
    ["Seccion", "Nombre", "Tipo_o_Sentido", "Min_o_RHS", "Max_o_Peso", "x1", "x2"],
    ["Variable", "x1", "continuous", 0, 10],
    ["Variable", "x2", "continuous", 0, 10],
    ["Objetivo", "Z1", "maximize", "", 0.5, 2, 3],
    ["Objetivo", "Z2", "minimize", "", 0.5, 1, 1],
    ["Restriccion", "R1", "<=", 5, "", { t: "n", f: "1/2", v: 0.5 }, 1],
  ]);
  const wbCached = xlsx.utils.book_new();
  xlsx.utils.book_append_sheet(wbCached, wsCached, "Modelo");
  const parsedCached = await importModelFromFile(
    fileFromBuffer(xlsx.write(wbCached, { type: "buffer", bookType: "xlsx" }), "cached.xlsx")
  );
  assert.equal(parsedCached.model.constraints[0].coefficients[0], 0.5);

  const aliasJson = JSON.stringify({
    name: "JSON con alias",
    variables: [{ name: "x1", var_type: "entera", lower_bound: 0, upper_bound: 10 }],
    objectives: [
      { name: "Z1", sense: "min", coefficients: [2] },
      { name: "Z2", sense: "max", coefficients: [3] },
    ],
    constraints: [{ name: "C1", sense: "=", coefficients: [1], rhs: 4 }],
    weights: [0.3, 0.7],
  });
  const parsedAlias = await importModelFromFile(fileFromBuffer(Buffer.from(aliasJson, "utf8"), "alias.json"));
  assert.equal(parsedAlias.model.variables[0].var_type, "integer");
  assert.equal(parsedAlias.model.objectives[0].sense, "minimize");
  assert.equal(parsedAlias.model.objectives[1].sense, "maximize");
  assert.equal(parsedAlias.model.constraints[0].sense, "==");
  assert.deepEqual(parsedAlias.weights, [0.3, 0.7]);

  await assert.rejects(
    () => importModelFromFile(fileFromBuffer(Buffer.from(JSON.stringify({
      variables: [{ name: "x1", var_type: "raro" }],
      objectives: [{ name: "Z1", sense: "max", coefficients: [1] }, { name: "Z2", sense: "min", coefficients: [1] }],
    })), "bad_vt.json")),
    /Tipo de variable desconocido/
  );
  await assert.rejects(
    () => importModelFromFile(fileFromBuffer(Buffer.from(JSON.stringify({
      variables: [{ name: "x1" }],
      objectives: [{ name: "Z1", sense: "max", coefficients: [1] }, { name: "Z2", sense: "min", coefficients: [1] }],
      weights: [0.2, 0.3, 0.5],
    })), "bad_w.json")),
    /exactamente 2 valores/
  );
});
