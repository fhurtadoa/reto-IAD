"""
Pruebas de exportación/plantillas Excel (.xlsx) y endpoint POST /api/export/excel.
Verifica:
- Generación y estructura de web/public/plantilla-ejercicio-iad.xlsx y ejercicios/*.xlsx.
- Ausencia de la palabra suelta 'Seccion' en las filas de título/subtítulo de 'Modelo'.
- Endpoint POST /api/export/excel con modelos estándar (01_celdas_fotovoltaicas, 06_produccion_papel)
  y el modelo adversarial con variables llamadas 'Seccion' (binary [1, 1]) y 'Nombre' ([0, 5]),
  dos objetivos homónimos 'Iguales', restricción '==' y pesos [0.6, 0.4].
"""
from __future__ import annotations

from base64 import b64encode
from copy import deepcopy
import json
import unittest
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader

from core.schemas import ConstraintModel, ModelDefinition, ObjectiveModel, VariableModel
from excel_export import build_upload_template_workbook
from index import app

ROOT_DIR = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT_DIR / "examples"
EXERCISES_DIR = ROOT_DIR / "ejercicios"
PUBLIC_DIR = ROOT_DIR / "web" / "public"


def _find_model_header_row(ws) -> tuple[int, list[str]]:
    for r_idx in range(1, ws.max_row + 1):
        row_vals = [ws.cell(row=r_idx, column=c_idx).value for c_idx in range(1, ws.max_column + 1)]
        if any(str(v or "").strip().lower() in {"seccion", "sección"} for v in row_vals):
            return r_idx, [str(v or "").strip() for v in row_vals]
    raise AssertionError("No se encontró fila de encabezado con 'Seccion' en la hoja Modelo.")


class TestExcelExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_upload_templates_structure_and_header_detection(self) -> None:
        raw = build_upload_template_workbook("blank")
        wb = load_workbook(BytesIO(raw), data_only=False)
        self.assertEqual(wb.sheetnames[0], "Modelo")
        self.assertIn("Guia_Docente", wb.sheetnames)

        ws = wb["Modelo"]
        self.assertEqual(ws.freeze_panes, "A4")
        header_idx, header = _find_model_header_row(ws)
        self.assertEqual(header_idx, 3, "plantilla-ejercicio-iad.xlsx: el encabezado debe estar exactamente en la fila 3")
        self.assertEqual(header[:5], ["Seccion", "Nombre", "Tipo_o_Sentido", "Min_o_RHS", "Max_o_Peso"])
        self.assertEqual(len([h for h in header[5:] if h]), 2)
        self.assertGreaterEqual(len(ws.data_validations.dataValidation), 2)

        public_path = PUBLIC_DIR / "plantilla-ejercicio-iad.xlsx"
        self.assertTrue(public_path.is_file(), f"Falta plantilla generada en {public_path}")
        wb_disk = load_workbook(public_path, data_only=False)
        self.assertEqual(wb_disk.sheetnames, ["Modelo", "Guia_Docente", "Ejemplo_Papel"])
        self.assertFalse(wb_disk["Modelo"]["B7"].value)
        self.assertFalse(wb_disk["Modelo"]["F7"].value)
        self.assertEqual(_find_model_header_row(wb_disk["Ejemplo_Papel"])[0], 3)
        self.assertTrue(wb_disk["Ejemplo_Papel"]["B4"].value)
        disk_header_idx, _ = _find_model_header_row(wb_disk["Modelo"])
        self.assertEqual(disk_header_idx, 3)

        # Verificar todos los ejercicios .xlsx generados desde examples/*.json
        json_files = sorted(EXAMPLES_DIR.glob("*.json"))
        self.assertEqual(len(json_files), 6)
        for json_path in json_files:
            model_dict = json.loads(json_path.read_text(encoding="utf-8-sig"))
            xlsx_path = EXERCISES_DIR / f"{json_path.stem}.xlsx"
            self.assertTrue(xlsx_path.is_file(), f"Falta ejercicio .xlsx en {xlsx_path}")
            wb_ex = load_workbook(xlsx_path, data_only=False)
            self.assertEqual(wb_ex.sheetnames, ["Modelo", "Guia_Docente"])
            ex_header_idx, ex_header = _find_model_header_row(wb_ex["Modelo"])
            self.assertEqual(ex_header_idx, 3)
            self.assertEqual(ex_header[:5], ["Seccion", "Nombre", "Tipo_o_Sentido", "Min_o_RHS", "Max_o_Peso"])
            self.assertEqual(len([h for h in ex_header[5:] if h]), len(model_dict["variables"]))
            for row_cells in wb_ex["Modelo"].iter_rows(min_row=ex_header_idx + 1, max_col=3):
                if row_cells[0].value == "Restriccion":
                    self.assertEqual(row_cells[2].data_type, "s")
                    self.assertIn(row_cells[2].value, {"<=", ">=", "=="})

    def test_export_excel_endpoint_standard_models(self) -> None:
        for example_name in ("01_celdas_fotovoltaicas.json", "06_produccion_papel.json"):
            model_dict = json.loads((EXAMPLES_DIR / example_name).read_text(encoding="utf-8"))
            solve_res = self.client.post("/api/solve", json=model_dict)
            self.assertEqual(solve_res.status_code, 200, solve_res.text)
            result_dict = solve_res.json()

            export_res = self.client.post("/api/export/excel", json={"model": model_dict, "result": result_dict})
            self.assertEqual(export_res.status_code, 200, export_res.text)
            self.assertEqual(
                export_res.headers.get("content-type"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.assertIn("attachment; filename=", export_res.headers.get("content-disposition", ""))

            wb = load_workbook(BytesIO(export_res.content), data_only=False)
            self.assertEqual(
                wb.sheetnames,
                ["Resumen_Ejecutivo", "Matriz_de_Pagos", "Soluciones_Compromiso", "Frontera_Pareto", "Modelo"],
            )

            # Validar formato de % Logro como decimal con formato 0.00%
            ws_sol = wb["Soluciones_Compromiso"]
            sol_headers = [ws_sol.cell(row=4, column=c).value for c in range(1, ws_sol.max_column + 1)]
            pct_cols = [idx + 1 for idx, h in enumerate(sol_headers) if str(h or "").startswith("% Logro:")]
            self.assertEqual(len(pct_cols), len(model_dict["objectives"]))
            for col in pct_cols:
                cell = ws_sol.cell(row=5, column=col)
                self.assertEqual(cell.number_format, "0.00%")
                self.assertIsInstance(cell.value, (int, float))
                self.assertLessEqual(abs(cell.value), 1.5)

            # Validar hoja Modelo re-importable
            ws_mod = wb["Modelo"]
            header_idx, header = _find_model_header_row(ws_mod)
            self.assertEqual(header_idx, 2)
            self.assertEqual(header[:5], ["Seccion", "Nombre", "Tipo_o_Sentido", "Min_o_RHS", "Max_o_Peso"])

    def test_reports_include_images_and_show_malformed_image_errors(self) -> None:
        model = json.loads((EXAMPLES_DIR / "01_celdas_fotovoltaicas.json").read_text(encoding="utf-8"))
        result = self.client.post("/api/solve", json=model).json()
        image = BytesIO()
        Image.new("RGB", (400, 200), "#e11d48").save(image, "PNG")
        chart = {"title": "Gráfica de prueba", "caption": "Dos ejes", "png": b64encode(image.getvalue()).decode()}
        payload = {
            "model": model,
            "result": result,
            "charts": [chart],
            "warnings": ["Vista 3D pendiente de generar."],
        }

        excel = self.client.post("/api/export/excel", json=payload)
        self.assertEqual(excel.status_code, 200)
        book = load_workbook(BytesIO(excel.content))
        drawing = book["G1 Gráfica de prueba"]._images[0]
        self.assertEqual(drawing._data(), image.getvalue())
        self.assertEqual(drawing.anchor.ext.cx, 2 * drawing.anchor.ext.cy)
        self.assertEqual(book["G1 Gráfica de prueba"]["A2"].value, "Dos ejes")
        self.assertIn("Gráficas pendientes", [cell.value for cell in book["Resumen_Ejecutivo"]["A"]])

        pdf = self.client.post("/api/export/pdf", json=payload)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers["content-type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertIn(b"/Subtype /Image", pdf.content)

        chart["png"] = "dato inválido"
        for format in ("excel", "pdf"):
            response = self.client.post(f"/api/export/{format}", json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertIn("imagen PNG válida", response.json()["detail"])

    def test_both_reports_reject_incomplete_or_nonfinite_snapshots(self) -> None:
        model = json.loads((EXAMPLES_DIR / "01_celdas_fotovoltaicas.json").read_text(encoding="utf-8"))
        result = self.client.post("/api/solve", json=model).json()
        invalid = {
            "payoff.headers": lambda r: r["payoff"]["headers"].pop(),
            "payoff.ideal_point": lambda r: r["payoff"]["ideal_point"].pop(),
            "payoff.anti_ideal_point": lambda r: r["payoff"]["anti_ideal_point"].pop(),
            "payoff.normalization_ranges": lambda r: r["payoff"]["normalization_ranges"].pop(),
            "payoff.matrix": lambda r: r["payoff"]["matrix"][0].pop(),
            "solutions.L1": lambda r: r["solutions"]["L1"]["variables"].clear(),
            "solutions.L2": lambda r: r["solutions"]["L2"]["normalized_distances"].pop(),
            "pareto_points[0]": lambda r: r["pareto_points"][0]["objectives"].pop(),
            "Desbordamiento numérico": lambda r: r["solutions"]["L1"].update(aggregate_distance=float("nan")),
            "result.payoff.matrix.0": lambda r: r["payoff"]["matrix"].__setitem__(0, float("inf")),
        }
        for format in ("excel", "pdf"):
            for expected, mutate in invalid.items():
                with self.subTest(format=format, field=expected):
                    malformed = deepcopy(result)
                    mutate(malformed)
                    response = self.client.post(
                        f"/api/export/{format}",
                        content=json.dumps({"model": model, "result": malformed}),
                        headers={"Content-Type": "application/json"},
                    )
                    self.assertIn(response.status_code, (400, 422), response.text)
                    self.assertIn(expected, response.json()["detail"])

    def test_both_reports_accept_genuine_partial_results(self) -> None:
        model = json.loads((EXAMPLES_DIR / "01_celdas_fotovoltaicas.json").read_text(encoding="utf-8"))
        result = self.client.post("/api/solve", json=model).json()
        result.update(status="partial")
        result["solutions"]["L2"].update(
            variables={}, objectives=[], normalized_distances=[], achievement_pct=[],
            aggregate_distance=0, status="error: falta un certificado factible",
        )
        for format in ("excel", "pdf"):
            response = self.client.post(f"/api/export/{format}", json={"model": model, "result": result})
            self.assertEqual(response.status_code, 200, response.text[:250])

    def test_excel_chart_names_are_safe_and_bounded(self) -> None:
        model = json.loads((EXAMPLES_DIR / "01_celdas_fotovoltaicas.json").read_text(encoding="utf-8"))
        result = self.client.post("/api/solve", json=model).json()
        image = BytesIO()
        Image.new("RGB", (40, 20)).save(image, "PNG")
        png = b64encode(image.getvalue()).decode()
        charts = [{"title": title, "png": png} for title in (
            "'\n\r[]:*?/\\", "'  A\r\n[ B ] " + 70 * "Z", "'", "A B",
        )]
        response = self.client.post("/api/export/excel", json={"model": model, "result": result, "charts": charts})
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(workbook.sheetnames[-4:], ["G1 Gráfica", "G2 A B " + 24 * "Z", "G3 Gráfica", "G4 A B"])
        self.assertTrue(all(len(workbook[name]._images) == 1 for name in workbook.sheetnames[-4:]))

    def test_pdf_embeds_unicode_and_both_filenames_preserve_accents_as_ascii(self) -> None:
        model = json.loads((EXAMPLES_DIR / "01_celdas_fotovoltaicas.json").read_text(encoding="utf-8"))
        model["name"] = "Producción de prueba"
        model["description"] = "Criterios Z₃ y Z₄ sobre ℝ y ℤ. A < B & C > D."
        model["objectives"][0]["name"] = "Z₃ & Z₄"
        result = self.client.post("/api/solve", json=model).json()
        payload = {"model": model, "result": result}
        for format, ext in (("excel", "xlsx"), ("pdf", "pdf")):
            response = self.client.post(f"/api/export/{format}", json=payload)
            self.assertEqual(response.status_code, 200, response.text[:250])
            self.assertIn(f"OptiCompromise_produccion_de_prueba.{ext}", response.headers["content-disposition"])
        pdf = PdfReader(BytesIO(response.content))
        extracted = "\n".join(page.extract_text() for page in pdf.pages)
        self.assertIn(model["description"], extracted)
        self.assertIn(model["objectives"][0]["name"], extracted)
        self.assertIn("Matriz de pagos y referencias", extracted)
        self.assertIn("Nadir aproximado", extracted)
        self.assertNotIn("■", extracted)
        self.assertNotIn("Interpretación", extracted)

        mip_model = json.loads((EXAMPLES_DIR / "03_mip_produccion.json").read_text(encoding="utf-8"))
        mip_result = self.client.post("/api/solve", json=mip_model).json()
        mip_result["solutions"]["L2"]["status"] = "feasible_suboptimal"
        mip_pdf = self.client.post("/api/export/pdf", json={"model": mip_model, "result": mip_result})
        self.assertEqual(mip_pdf.status_code, 200)
        mip_text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(mip_pdf.content)).pages)
        self.assertIn("y1", mip_text)
        self.assertIn("150 · y1", mip_text)

        mip_excel = self.client.post("/api/export/excel", json={"model": mip_model, "result": mip_result})
        self.assertEqual(mip_excel.status_code, 200)
        wb_mip = load_workbook(BytesIO(mip_excel.content), data_only=False)
        summary_values = [cell.value for row in wb_mip["Resumen_Ejecutivo"].iter_rows() for cell in row]
        self.assertIn("Nadir aproximado (Z_peor)", summary_values)
        self.assertIn("Factible sin certificado (feasible_suboptimal)", summary_values)

    def test_export_excel_endpoint_adversarial_reserved_names_and_bounds(self) -> None:
        adversarial = ModelDefinition(
            name="Modelo Adversarial Codex",
            description="Variables con nombres reservados y objetivos homónimos.",
            reference="Prueba Adversarial Track 1",
            variables=[
                VariableModel(name="Seccion", var_type="binary", lower_bound=1.0, upper_bound=1.0),
                VariableModel(name="Nombre", var_type="continuous", lower_bound=0.0, upper_bound=5.0),
            ],
            objectives=[
                ObjectiveModel(name="Iguales", sense="maximize", coefficients=[10.0, 2.0]),
                ObjectiveModel(name="Iguales", sense="minimize", coefficients=[1.0, 3.0]),
            ],
            constraints=[
                ConstraintModel(name="Igualdad Exacta", sense="==", rhs=4.0, coefficients=[1.0, 1.0]),
            ],
            weights=[0.6, 0.4],
            pareto_seed=77,
        )

        model_dict = adversarial.model_dump()
        solve_res = self.client.post("/api/solve", json=model_dict)
        self.assertEqual(solve_res.status_code, 200, solve_res.text)
        result_dict = solve_res.json()

        export_res = self.client.post("/api/export/excel", json={"model": model_dict, "result": result_dict})
        self.assertEqual(export_res.status_code, 200, export_res.text)

        wb = load_workbook(BytesIO(export_res.content), data_only=False)
        ws_mod = wb["Modelo"]
        header_idx, header = _find_model_header_row(ws_mod)
        self.assertEqual(header_idx, 2)
        self.assertEqual(
            header,
            ["Seccion", "Nombre", "Tipo_o_Sentido", "Min_o_RHS", "Max_o_Peso", "Coef: Seccion", "Coef: Nombre"],
        )

        rows = []
        for r_idx in range(header_idx + 1, ws_mod.max_row + 1):
            rows.append([ws_mod.cell(row=r_idx, column=c).value for c in range(1, len(header) + 1)])

        # Meta
        meta_row = rows[0]
        self.assertEqual(meta_row[0], "Meta")
        self.assertEqual(meta_row[1], "Modelo Adversarial Codex")
        self.assertEqual(meta_row[3], 77)
        self.assertEqual(meta_row[4], "Prueba Adversarial Track 1")

        # Variables
        var_rows = [r for r in rows if r[0] == "Variable"]
        self.assertEqual(len(var_rows), 2)
        self.assertEqual(var_rows[0][:5], ["Variable", "Seccion", "binary", 1, 1])
        self.assertEqual(var_rows[1][:5], ["Variable", "Nombre", "continuous", 0, 5])

        # Objetivos homónimos y pesos
        obj_rows = [r for r in rows if r[0] == "Objetivo"]
        self.assertEqual(len(obj_rows), 2)
        self.assertEqual(obj_rows[0], ["Objetivo", "Iguales", "maximize", None, 0.6, 10, 2])
        self.assertEqual(obj_rows[1], ["Objetivo", "Iguales", "minimize", None, 0.4, 1, 3])

        # Restricción ==
        con_rows = [r for r in rows if r[0] == "Restriccion"]
        self.assertEqual(len(con_rows), 1)
        self.assertEqual(con_rows[0], ["Restriccion", "Igualdad Exacta", "==", 4, None, 1, 1])


if __name__ == "__main__":
    unittest.main()
