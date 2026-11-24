"""
Generación de libros Excel (.xlsx) con estética editorial UNAL / OptiCompromise:
- Plantilla de carga con ejemplo de consulta dentro del libro.
- Reportes completos de resultados multiobjetivo con hoja Modelo 100% re-importable.
"""
from __future__ import annotations

from io import BytesIO
from math import ceil
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

try:
    from .core.schemas import ModelDefinition, SolveResponse
    from .report_images import ChartImage, report_text
except (ImportError, ValueError):
    from core.schemas import ModelDefinition, SolveResponse
    from report_images import ChartImage, report_text

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"

MODEL_COLUMNS = ["Seccion", "Nombre", "Tipo_o_Sentido", "Min_o_RHS", "Max_o_Peso"]
RESERVED_MODEL_COLUMNS = {
    *[c.lower() for c in MODEL_COLUMNS],
    "sección",
    "tipo",
    "elemento",
    "name",
    "variable",
    "description",
    "descripcion",
    "pareto_seed",
    "referencia",
    "fuente",
    "var_type",
    "tipo_var",
    "min",
    "max",
    "lower_bound",
    "upper_bound",
    "lb",
    "ub",
    "sense",
    "sentido",
    "peso",
    "weight",
    "operador",
    "rhs",
    "ld",
    "__proto__",
}

# Paleta editorial UNAL / OptiCompromise
NAVY_HEX = "111524"
SLATE_HEADER_HEX = "1E293B"
ROSE_ACCENT_HEX = "E11D48"
SOFT_SLATE_HEX = "F8FAFC"
BORDER_HEX = "CBD5E1"

SECTION_FILLS = {
    "Meta": PatternFill("solid", fgColor="FFF1F2"),
    "Variable": PatternFill("solid", fgColor="EFF6FF"),
    "Objetivo": PatternFill("solid", fgColor="ECFDF5"),
    "Restriccion": PatternFill("solid", fgColor="FFFBEB"),
}
SECTION_TEXT_COLORS = {
    "Meta": "9F1239",
    "Variable": "1E3A8A",
    "Objetivo": "065F46",
    "Restriccion": "92400E",
}

BANNER_FILL = PatternFill("solid", fgColor=NAVY_HEX)
SUBTITLE_FILL = PatternFill("solid", fgColor=SOFT_SLATE_HEX)
TABLE_HEADER_FILL = PatternFill("solid", fgColor=SLATE_HEADER_HEX)
ALT_ROW_FILL = PatternFill("solid", fgColor="F8FAFC")
DIAGONAL_FILL = PatternFill("solid", fgColor="ECFDF5")
IDEAL_FILL = PatternFill("solid", fgColor="FFFBEB")
NADIR_FILL = PatternFill("solid", fgColor="FFF1F2")
RANGE_FILL = PatternFill("solid", fgColor="F1F5F9")
ACCENT_FILL = PatternFill("solid", fgColor=ROSE_ACCENT_HEX)

THIN_SIDE = Side(border_style="thin", color=BORDER_HEX)
ACCENT_BOTTOM = Side(border_style="medium", color=ROSE_ACCENT_HEX)
GRID_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
HEADER_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=ACCENT_BOTTOM)

FONT_BANNER = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
FONT_SUBTITLE = Font(name="Calibri", size=10, italic=True, color="334155")
FONT_SECTION_TITLE = Font(name="Calibri", size=11, bold=True, color=NAVY_HEX)
FONT_TH = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
FONT_BODY = Font(name="Calibri", size=10, bold=False, color="0F172A")
FONT_BODY_BOLD = Font(name="Calibri", size=10, bold=True, color="0F172A")
FONT_DIAGONAL = Font(name="Calibri", size=10, bold=True, color="065F46")
FONT_IDEAL = Font(name="Calibri", size=10, bold=True, color="92400E")
FONT_NADIR = Font(name="Calibri", size=10, bold=True, color="9F1239")

ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=True)

STATUS_LABELS = {
    "optimal": "Óptimo",
    "partial": "Parcial",
    "feasible_suboptimal": "Factible sin certificado",
    "infeasible": "Infactible",
    "unbounded": "No acotado",
    "error": "Error",
}

METRIC_LABELS = {
    "L1": "L1 · Manhattan (Máxima eficiencia agregada)",
    "L2": "L2 · Euclidiana (Balance intermedio)",
    "L_inf": "L∞ · Chebyshev / Minimax (Máxima equidad)",
}

NORM_SOURCE_LABELS = {
    "payoff": "Matriz de pagos (Ideal - Nadir)",
    "feasible_range": "Rango factible del objetivo",
    "constant": "Objetivo constante (rango nulo)",
    "unit": "Escala unitaria de respaldo",
}


def coefficient_column(name: str) -> str:
    """Prefija nombres reservados exactamente igual que mathUtils.ts."""
    if name.strip().lower() in RESERVED_MODEL_COLUMNS or name.startswith("Coef: "):
        return f"Coef: {name}"
    return name


def _num_format(val: Any, default_fmt: str) -> str:
    if isinstance(val, (int, float)) and val != 0 and (abs(val) < 1e-4 or abs(val) >= 1e12):
        return "0.000E+00"
    return default_fmt


def _format_status(status: str | None) -> str:
    raw = (status or "").strip()
    if not raw:
        return "Sin estado"
    lower = raw.lower()
    if lower in STATUS_LABELS:
        return f"{STATUS_LABELS[lower]} ({raw})"
    if lower.startswith("error"):
        return f"Error ({raw})"
    return f"Sin confirmar ({raw})"


def _style_banner(ws: Worksheet, title: str, subtitle: str | None, col_count: int) -> int:
    """Escribe título y subtítulo editorial sin usar la palabra suelta 'Seccion'."""
    last_col = max(col_count, 5)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    c1 = ws.cell(row=1, column=1, value=title)
    c1.font = FONT_BANNER
    c1.fill = BANNER_FILL
    c1.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    if subtitle is not None:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
        c2 = ws.cell(row=2, column=1, value=subtitle)
        c2.font = FONT_SUBTITLE
        c2.fill = SUBTITLE_FILL
        c2.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
        c2.border = Border(bottom=ACCENT_BOTTOM)
        ws.row_dimensions[2].height = 24
        return 3
    return 2


def _autofit_columns(
    ws: Worksheet,
    min_width: int = 11,
    max_width: int = 44,
    skip_merged_rows: Iterable[int] = (1, 2),
) -> None:
    skip_set = set(skip_merged_rows)
    merged_coords = {
        (r, c)
        for rng in ws.merged_cells.ranges
        for r in range(rng.min_row, rng.max_row + 1)
        for c in range(rng.min_col, rng.max_col + 1)
    }
    for col_idx in range(1, ws.max_column + 1):
        best = min_width
        for row_idx in range(1, ws.max_row + 1):
            if row_idx in skip_set or (row_idx, col_idx) in merged_coords:
                continue
            val = ws.cell(row=row_idx, column=col_idx).value
            if val is None or val == "":
                continue
            text = str(val)
            longest_line = max((len(line) for line in text.splitlines()), default=0)
            # Números formateados suelen ser más compactos que su str largo
            if isinstance(val, float):
                longest_line = min(longest_line, 14)
            best = max(best, min(max_width, longest_line + 4))
        ws.column_dimensions[get_column_letter(col_idx)].width = best


def _write_model_sheet(
    ws: Worksheet,
    model: ModelDefinition,
    weights: Sequence[float] | None,
    banner_title: str,
    subtitle: str | None = None,
    extra_editable_rows: int = 0,
    blank: bool = False,
) -> None:
    """Escribe la hoja 'Modelo' 100% compatible con importModelFromFile."""
    var_cols = [coefficient_column(v.name) for v in model.variables]
    headers = [*MODEL_COLUMNS, *var_cols]

    header_row_idx = _style_banner(ws, banner_title, subtitle, len(headers))

    for col_idx, col_name in enumerate(headers, start=1):
        cell = ws.cell(row=header_row_idx, column=col_idx, value=col_name)
        cell.font = FONT_TH
        cell.fill = TABLE_HEADER_FILL
        cell.alignment = ALIGN_CENTER if col_idx <= 5 else ALIGN_RIGHT
        cell.border = HEADER_BORDER
    ws.row_dimensions[header_row_idx].height = 24

    eff_weights: list[float]
    if weights and len(weights) == len(model.objectives):
        eff_weights = list(weights)
    elif model.weights and len(model.weights) == len(model.objectives):
        eff_weights = list(model.weights)
    else:
        n_obj = max(len(model.objectives), 1)
        eff_weights = [round(1.0 / n_obj, 6) for _ in model.objectives]

    rows_payload: list[tuple[str, list[Any]]] = []

    rows_payload.append(
        (
            "Meta",
            [
                "Meta",
                model.name,
                model.description or "",
                model.pareto_seed,
                model.reference or "",
                *["" for _ in model.variables],
            ],
        )
    )

    for v in model.variables:
        if v.var_type == "binary":
            lb: Any = 0.0 if v.lower_bound is None else v.lower_bound
            ub: Any = 1.0 if v.upper_bound is None else v.upper_bound
        else:
            lb = "-inf" if v.lower_bound is None else v.lower_bound
            ub = "+inf" if v.upper_bound is None else v.upper_bound
        rows_payload.append(
            (
                "Variable",
                [
                    "Variable",
                    v.name,
                    v.var_type,
                    lb,
                    ub,
                    *["" for _ in model.variables],
                ],
            )
        )

    for idx, o in enumerate(model.objectives):
        coeffs = [o.coefficients[j] if j < len(o.coefficients) else 0.0 for j in range(len(model.variables))]
        rows_payload.append(
            (
                "Objetivo",
                [
                    "Objetivo",
                    o.name,
                    o.sense,
                    "",
                    eff_weights[idx],
                    *coeffs,
                ],
            )
        )

    for c in model.constraints:
        coeffs = [c.coefficients[j] if j < len(c.coefficients) else 0.0 for j in range(len(model.variables))]
        rows_payload.append(
            (
                "Restriccion",
                [
                    "Restriccion",
                    c.name,
                    c.sense,
                    c.rhs,
                    "",
                    *coeffs,
                ],
            )
        )

    if blank:
        rows_payload = [
            (section, values if section == "Variable" else [section, *[""] * (len(headers) - 1)])
            for section, values in rows_payload
        ]

    first_data_row = header_row_idx + 1
    current_row = first_data_row
    for sec, values in rows_payload:
        fill = SECTION_FILLS[sec]
        sec_color = SECTION_TEXT_COLORS[sec]
        for col_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=current_row, column=col_idx, value=val)
            # Evita que cadenas como "==" se serialicen como fórmulas vacías ("f") al abrir con SheetJS/Excel.
            if isinstance(val, str):
                cell.data_type = "s"
            cell.fill = fill
            cell.border = GRID_BORDER
            if col_idx == 1:
                cell.font = Font(name="Calibri", size=10, bold=True, color=sec_color)
                cell.alignment = ALIGN_CENTER
            elif col_idx == 2:
                cell.font = FONT_BODY_BOLD
                cell.alignment = ALIGN_LEFT
            elif col_idx == 3:
                cell.font = FONT_BODY
                cell.alignment = ALIGN_LEFT if sec == "Meta" else ALIGN_CENTER
                if sec == "Restriccion":
                    cell.number_format = "@"
            elif col_idx in (4, 5):
                cell.font = FONT_BODY
                if isinstance(val, (int, float)):
                    cell.alignment = ALIGN_RIGHT
                    cell.number_format = "#,##0.####"
                else:
                    cell.alignment = ALIGN_CENTER if sec != "Meta" else ALIGN_LEFT
            else:
                cell.font = FONT_BODY
                if isinstance(val, (int, float)):
                    cell.alignment = ALIGN_RIGHT
                    cell.number_format = "#,##0.####"
                else:
                    cell.alignment = ALIGN_RIGHT
        if sec == "Meta" and len(str(values[2])) > 75:
            ws.row_dimensions[current_row].height = 38
        else:
            ws.row_dimensions[current_row].height = 20
        current_row += 1

    # Filas extra limpias (solo si es plantilla de carga)
    if extra_editable_rows > 0:
        for _ in range(extra_editable_rows):
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=current_row, column=col_idx, value="")
                cell.border = GRID_BORDER
                cell.font = FONT_BODY
            ws.row_dimensions[current_row].height = 20
            current_row += 1

    last_row = current_row - 1
    ws.freeze_panes = f"A{first_data_row}"
    ws.views.sheetView[0].showGridLines = True

    # Validaciones de datos desplegables en Excel
    dv_sec = DataValidation(
        type="list",
        formula1='"Meta,Variable,Objetivo,Restriccion"',
        allow_blank=True,
        errorStyle="warning",
        promptTitle="Sección de fila",
        prompt="Elige Meta, Variable, Objetivo o Restriccion.",
    )
    ws.add_data_validation(dv_sec)
    dv_sec.add(f"A{first_data_row}:A{max(last_row, first_data_row + 20)}")

    # Consejos y listas desplegables contextuales para Tipo_o_Sentido
    for r_idx, (sec, _) in enumerate(rows_payload, start=first_data_row):
        if sec == "Variable":
            dv = DataValidation(
                type="list",
                formula1='"continuous,integer,binary"',
                allow_blank=False,
                promptTitle="Tipo de variable",
                prompt="Usa continuous, integer o binary.",
            )
            ws.add_data_validation(dv)
            dv.add(f"C{r_idx}")
        elif sec == "Objetivo":
            dv = DataValidation(
                type="list",
                formula1='"maximize,minimize"',
                allow_blank=False,
                promptTitle="Sentido del objetivo",
                prompt="Usa maximize o minimize.",
            )
            ws.add_data_validation(dv)
            dv.add(f"C{r_idx}")
        elif sec == "Restriccion":
            dv = DataValidation(
                type="list",
                formula1='"<=,>=,=="',
                allow_blank=False,
                promptTitle="Operador de restricción",
                prompt="Usa <=, >= o ==.",
            )
            ws.add_data_validation(dv)
            dv.add(f"C{r_idx}")

    extra_start = first_data_row + len(rows_payload)
    extra_end = max(last_row, extra_start + 20)
    dv_hint = DataValidation(
        type="list",
        formula1='"continuous,integer,binary,maximize,minimize,<=,>=,=="',
        allow_blank=True,
        errorStyle="information",
        promptTitle="Valores válidos en Tipo_o_Sentido",
        prompt="Variable: continuous/integer/binary | Objetivo: maximize/minimize | Restriccion: <=, >=, ==",
    )
    ws.add_data_validation(dv_hint)
    dv_hint.add(f"C{extra_start}:C{extra_end}")

    _autofit_columns(ws, min_width=12, max_width=46, skip_merged_rows=range(1, header_row_idx))


def _write_guide_sheet(ws: Worksheet) -> None:
    """Hoja Guia_Docente para plantillas de carga."""
    _style_banner(
        ws,
        "Guía Rápida — Formulación de Modelos Multiobjetivo en Excel (IAD · UNAL)",
        "Referencia de columnas, valores permitidos y buenas prácticas para importar en OptiCompromise.",
        4,
    )

    # Tabla 1: Estructura de columnas
    ws.cell(row=4, column=1, value="1. Estructura de columnas de la hoja Modelo").font = FONT_SECTION_TITLE
    col_headers = ["Columna", "Aplica a", "Qué escribir", "Ejemplo"]
    for c_idx, h in enumerate(col_headers, start=1):
        cell = ws.cell(row=5, column=c_idx, value=h)
        cell.font = FONT_TH
        cell.fill = TABLE_HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = HEADER_BORDER
    ws.row_dimensions[5].height = 22

    col_rows = [
        ("Seccion", "Todas las filas", "Define el tipo de fila: Meta, Variable, Objetivo o Restriccion.", "Variable"),
        ("Nombre", "Todas las filas", "Nombre del modelo, variable (único), objetivo o restricción.", "x1 (Planta A)"),
        ("Tipo_o_Sentido", "Según Sección", "Meta: descripción | Variable: tipo | Objetivo: sentido | Restriccion: operador.", "maximize / <="),
        ("Min_o_RHS", "Meta / Var / Rest.", "Meta: semilla Pareto (42) | Variable: cota inferior (-inf si libre) | Restriccion: lado derecho (RHS).", "0 / 100 / -inf"),
        ("Max_o_Peso", "Meta / Var / Obj.", "Meta: fuente académica | Variable: cota superior (+inf si libre) | Objetivo: peso w_i (0..1).", "+inf / 0.5"),
        ("Columnas de variables", "Objetivo / Rest.", "Un encabezado por cada variable del modelo con su coeficiente lineal (vacío = 0).", "76 / 1 / 0"),
    ]
    for offset, row_vals in enumerate(col_rows):
        r = 6 + offset
        fill = ALT_ROW_FILL if offset % 2 else PatternFill(fill_type=None)
        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=r, column=c_idx, value=val)
            cell.font = FONT_BODY_BOLD if c_idx == 1 else FONT_BODY
            cell.alignment = ALIGN_LEFT
            cell.border = GRID_BORDER
            if fill.fill_type:
                cell.fill = fill
        ws.row_dimensions[r].height = 28

    # Tabla 2: Valores permitidos
    start_t2 = 13
    ws.cell(row=start_t2, column=1, value="2. Valores permitidos y palabras clave").font = FONT_SECTION_TITLE
    val_headers = ["Categoría", "Valores aceptados", "Significado", "Notas"]
    for c_idx, h in enumerate(val_headers, start=1):
        cell = ws.cell(row=start_t2 + 1, column=c_idx, value=h)
        cell.font = FONT_TH
        cell.fill = TABLE_HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = HEADER_BORDER
    ws.row_dimensions[start_t2 + 1].height = 22

    val_rows = [
        ("Tipo de variable", "continuous | integer | binary", "Continua (ℝ), Entera (ℤ) o Binaria ({0, 1})", "También acepta continua, entera, binaria."),
        ("Sentido objetivo", "maximize | minimize", "Maximizar o minimizar la función Z_i", "También acepta max / min / maximizar / minimizar."),
        ("Operador restricción", "<= | >= | ==", "Menor o igual, mayor o igual o igualdad", "También acepta =, ≤ o ≥."),
        ("Cotas no acotadas", "-inf | +inf", "Sin límite inferior o sin límite superior", "Para binary sin cotas personalizadas se usa [0, 1]."),
    ]
    for offset, row_vals in enumerate(val_rows):
        r = start_t2 + 2 + offset
        fill = ALT_ROW_FILL if offset % 2 else PatternFill(fill_type=None)
        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=r, column=c_idx, value=val)
            cell.font = FONT_BODY_BOLD if c_idx == 1 else FONT_BODY
            cell.alignment = ALIGN_LEFT
            cell.border = GRID_BORDER
            if fill.fill_type:
                cell.fill = fill
        ws.row_dimensions[r].height = 24

    # Tabla 3: Trucos y flujo de importación
    start_t3 = 20
    ws.cell(row=start_t3, column=1, value="3. Consejos prácticos e importación en la plataforma").font = FONT_SECTION_TITLE
    tips = [
        ("Pesos vacíos = pesos iguales", "Si dejas vacía la columna Max_o_Peso en todos los objetivos, OptiCompromise asignará pesos iguales (1/q). Si ingresas un peso, completa todos para que sumen 1."),
        ("Nombres reservados de variables", "Si una variable se llama exactamente Seccion, Nombre, Tipo_o_Sentido, Min_o_RHS, Max_o_Peso, min, max, peso, etc., nombra su columna de coeficientes como «Coef: <nombre>»."),
        ("Cómo importar en la web", "En «Formular», pulsa «Cargar ejercicio». Solo se lee la hoja «Modelo». Usa «Ejemplo_Papel» como referencia."),
        ("Re-importación de resultados", "Todo libro de resultados descargado desde OptiCompromise incluye una hoja «Modelo» fiel que puedes ajustar y volver a importar sin pérdida de datos."),
    ]
    for offset, (title_tip, desc_tip) in enumerate(tips):
        r = start_t3 + 1 + offset
        c1 = ws.cell(row=r, column=1, value=title_tip)
        c1.font = FONT_BODY_BOLD
        c1.fill = SECTION_FILLS["Meta"]
        c1.alignment = ALIGN_LEFT
        c1.border = GRID_BORDER
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        for c_idx in range(2, 5):
            cell = ws.cell(row=r, column=c_idx)
            cell.border = GRID_BORDER
            cell.fill = SUBTITLE_FILL
        c2 = ws.cell(row=r, column=2, value=desc_tip)
        c2.font = FONT_BODY
        c2.alignment = ALIGN_LEFT
        ws.row_dimensions[r].height = 30

    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 52
    ws.column_dimensions["D"].width = 34
    ws.freeze_panes = "A4"


def _build_blank_template_model() -> ModelDefinition:
    return ModelDefinition(
        name="",
        variables=[
            {"name": "x1", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": None},
            {"name": "x2", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": None},
        ],
        objectives=[
            {"name": "", "sense": "maximize"},
            {"name": "", "sense": "minimize"},
        ],
    )


def _load_papel_model() -> ModelDefinition:
    path = EXAMPLES_DIR / "06_produccion_papel.json"
    return ModelDefinition.model_validate_json(path.read_text(encoding="utf-8-sig"))


def _workbook_to_bytes(wb: Workbook) -> bytes:
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_upload_template_workbook(variant: str = "blank") -> bytes:
    """Genera una plantilla Excel (.xlsx) lista para editar e importar en OptiCompromise."""
    if variant not in {"blank", "papel"}:
        raise ValueError(f"Variante no soportada: '{variant}'. Usa 'blank' o 'papel'.")

    wb = Workbook()
    ws_model = wb.active
    ws_model.title = "Modelo"

    if variant == "blank":
        model = _build_blank_template_model()
        subtitle = (
            "Diligencia esta hoja antes de cargar el archivo. "
            "Consulta Guia_Docente y Ejemplo_Papel para ver cómo completar los datos."
        )
        extra_rows = 8
    else:
        model = _load_papel_model()
        subtitle = (
            "Ejemplo precargado (Producción de papel · Taller 1/3 IAD). "
            "Ajusta demanda, costos, calidades o pesos y cárgalo en «Cargar ejercicio»."
        )
        extra_rows = 4

    _write_model_sheet(
        ws_model,
        model=model,
        weights=model.weights,
        banner_title="OptiCompromise — Plantilla de Carga de Modelo Multiobjetivo (IAD · UNAL)",
        subtitle=subtitle,
        extra_editable_rows=extra_rows,
        blank=variant == "blank",
    )

    _write_guide_sheet(wb.create_sheet("Guia_Docente"))
    if variant == "blank":
        paper = _load_papel_model()
        _write_model_sheet(
            wb.create_sheet("Ejemplo_Papel"),
            paper,
            paper.weights,
            "Ejemplo de consulta | Producción de papel",
            "Esta hoja contiene datos de referencia. OptiCompromise carga únicamente la hoja Modelo.",
        )
    return _workbook_to_bytes(wb)


def build_exercise_workbook(model: ModelDefinition) -> bytes:
    """Genera un libro Excel (.xlsx) autocontenido y re-importable para un ejercicio oficial."""
    wb = Workbook()
    ws_model = wb.active
    ws_model.title = "Modelo"
    _write_model_sheet(
        ws_model,
        model=model,
        weights=model.weights,
        banner_title=f"OptiCompromise — {model.name}",
        subtitle=(
            "Ejercicio oficial listo para abrir con «Cargar ejercicio» en Formular. "
            "Edita coeficientes, cotas o pesos en la hoja Modelo."
        ),
        extra_editable_rows=4,
        blank=False,
    )
    _write_guide_sheet(wb.create_sheet("Guia_Docente"))
    return _workbook_to_bytes(wb)


def _write_summary_sheet(ws: Worksheet, model: ModelDefinition, result: SolveResponse) -> None:
    _style_banner(
        ws,
        "OptiCompromise — Resumen Ejecutivo de Resultados",
        "Universidad Nacional de Colombia · Facultad de Minas · Introducción al Análisis de Decisiones (IAD)",
        7,
    )

    # Bloque 1: Metadatos del modelo y estado del solver
    ws.cell(row=4, column=1, value="1. Ficha del Modelo y Diagnóstico del Solver").font = FONT_SECTION_TITLE
    meta_rows = [
        ("Nombre del modelo", model.name),
        ("Descripción", model.description or "—"),
        ("Fuente académica", model.reference or "—"),
        (
            "Dimensiones",
            f"{len(model.variables)} variables · {len(model.objectives)} objetivos · {len(model.constraints)} restricciones",
        ),
        ("Estado general del solver", _format_status(result.status)),
        ("Mensaje del solver", result.message),
    ]
    for offset, (label, val) in enumerate(meta_rows):
        r = 5 + offset
        c1 = ws.cell(row=r, column=1, value=label)
        c1.font = FONT_BODY_BOLD
        c1.fill = SUBTITLE_FILL
        c1.alignment = ALIGN_LEFT
        c1.border = GRID_BORDER

        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
        for c_idx in range(2, 8):
            ws.cell(row=r, column=c_idx).border = GRID_BORDER
        c2 = ws.cell(row=r, column=2, value=val)
        c2.font = FONT_BODY_BOLD if offset == 4 else FONT_BODY
        c2.alignment = ALIGN_LEFT
        if offset == 4:
            c2.fill = DIAGONAL_FILL if result.status == "optimal" else NADIR_FILL
        ws.row_dimensions[r].height = 30 if len(str(val)) > 85 else 21

    # Bloque 2: Preferencias / Pesos
    start_w = 12
    ws.cell(row=start_w, column=1, value="2. Preferencias del Decisor (Vector de Pesos)").font = FONT_SECTION_TITLE
    w_headers = ["#", "Objetivo", "Sentido", "Peso (w_i)", "Punto Ideal (Z*)", "Nadir aproximado (Z_peor)", "Rango de Conflicto (R_i)"]
    for c_idx, h in enumerate(w_headers, start=1):
        cell = ws.cell(row=start_w + 1, column=c_idx, value=h)
        cell.font = FONT_TH
        cell.fill = TABLE_HEADER_FILL
        cell.alignment = ALIGN_CENTER if c_idx in (1, 3) else (ALIGN_RIGHT if c_idx >= 4 else ALIGN_LEFT)
        cell.border = HEADER_BORDER
    ws.row_dimensions[start_w + 1].height = 22

    r_ranges = result.payoff.normalization_ranges or [
        abs(result.payoff.ideal_point[i] - result.payoff.anti_ideal_point[i])
        for i in range(len(model.objectives))
    ]
    for idx, obj in enumerate(model.objectives):
        r = start_w + 2 + idx
        w_val = result.weights[idx] if idx < len(result.weights) else 1.0 / max(len(model.objectives), 1)
        ideal_val = result.payoff.ideal_point[idx] if idx < len(result.payoff.ideal_point) else None
        nadir_val = result.payoff.anti_ideal_point[idx] if idx < len(result.payoff.anti_ideal_point) else None
        rng_val = r_ranges[idx] if idx < len(r_ranges) else None
        sense_txt = "Maximizar" if obj.sense == "maximize" else "Minimizar"
        row_vals: list[Any] = [idx + 1, obj.name, sense_txt, w_val, ideal_val, nadir_val, rng_val]
        fill = ALT_ROW_FILL if idx % 2 else PatternFill(fill_type=None)
        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=r, column=c_idx, value=val)
            cell.font = FONT_BODY_BOLD if c_idx == 2 else FONT_BODY
            cell.border = GRID_BORDER
            if fill.fill_type:
                cell.fill = fill
            if c_idx in (1, 3):
                cell.alignment = ALIGN_CENTER
            elif c_idx == 2:
                cell.alignment = ALIGN_LEFT
            else:
                cell.alignment = ALIGN_RIGHT
                if c_idx == 4:
                    cell.number_format = "0.00%"
                elif isinstance(val, (int, float)):
                    cell.number_format = _num_format(val, "#,##0.00##")
        ws.row_dimensions[r].height = 20

    # Bloque 3: Comparativa L1, L2, L_inf
    start_m = start_w + 3 + len(model.objectives)
    ws.cell(row=start_m, column=1, value="3. Comparativa de Métricas de Compromiso (L1, L2, L∞)").font = FONT_SECTION_TITLE
    m_headers = ["Métrica", "Criterio / Enfoque", "Estado", "Distancia D_p", "Logro Promedio", "Certificado / Observación"]
    for c_idx, h in enumerate(m_headers, start=1):
        cell = ws.cell(row=start_m + 1, column=c_idx, value=h)
        cell.font = FONT_TH
        cell.fill = TABLE_HEADER_FILL
        cell.alignment = ALIGN_CENTER if c_idx in (1, 3) else (ALIGN_RIGHT if c_idx in (4, 5) else ALIGN_LEFT)
        cell.border = HEADER_BORDER
    ws.row_dimensions[start_m + 1].height = 22

    for idx, key in enumerate(("L1", "L2", "L_inf")):
        r = start_m + 2 + idx
        sol = result.solutions.get(key)
        if sol is None:
            row_vals = [key, METRIC_LABELS.get(key, key), "No disponible", None, None, "Métrica no incluida en respuesta"]
        else:
            avg_ach = (
                sum(value / 100.0 / len(sol.achievement_pct) for value in sol.achievement_pct)
                if sol.achievement_pct
                else None
            )
            engine_name = "SLSQP / Branch-and-Bound (QP/MIQP)" if key == "L2" else "HiGHS (LP/MILP)"
            cert = (
                f"Optimalidad certificada ({engine_name})"
                if sol.status == "optimal"
                else (
                    f"Factible sin certificado de optimalidad ({engine_name})"
                    if sol.status == "feasible_suboptimal"
                    else f"Revisar estado del solver: {sol.status}"
                )
            )
            dist_val = sol.aggregate_distance if sol.objectives else None
            row_vals = [
                "L∞" if key == "L_inf" else key,
                METRIC_LABELS.get(key, key),
                _format_status(sol.status),
                dist_val,
                avg_ach,
                cert,
            ]
        fill = ALT_ROW_FILL if idx % 2 else PatternFill(fill_type=None)
        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=r, column=c_idx, value=val)
            cell.font = FONT_BODY_BOLD if c_idx == 1 else FONT_BODY
            cell.border = GRID_BORDER
            if fill.fill_type:
                cell.fill = fill
            if c_idx in (1, 3):
                cell.alignment = ALIGN_CENTER
            elif c_idx in (4, 5):
                cell.alignment = ALIGN_RIGHT
                if isinstance(val, (int, float)):
                    cell.number_format = "0.00%" if c_idx == 5 else _num_format(val, "0.0000")
            else:
                cell.alignment = ALIGN_LEFT
        ws.row_dimensions[r].height = 21

    ws.freeze_panes = "A4"
    _autofit_columns(ws, min_width=13, max_width=44, skip_merged_rows=(1, 2, 5, 6, 7, 8, 9, 10))
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = max(ws.column_dimensions["B"].width or 24, 34)


def _write_payoff_sheet(ws: Worksheet, result: SolveResponse) -> None:
    payoff = result.payoff
    headers = payoff.headers
    n_cols = max(len(headers) + 1, 4)

    _style_banner(
        ws,
        "Matriz de Pagos — Óptimos Individuales, Punto Ideal y Nadir",
        "La diagonal principal (en verde) muestra el valor óptimo individual Z*_i alcanzado al optimizar cada objetivo por separado.",
        n_cols,
    )

    table_headers = ["Solución Óptima de:", *headers]
    for c_idx, h in enumerate(table_headers, start=1):
        cell = ws.cell(row=4, column=c_idx, value=h)
        cell.font = FONT_TH
        cell.fill = TABLE_HEADER_FILL
        cell.alignment = ALIGN_LEFT if c_idx == 1 else ALIGN_RIGHT
        cell.border = HEADER_BORDER
    ws.row_dimensions[4].height = 24

    current_row = 5
    for i, row_vals in enumerate(payoff.matrix):
        row_label = headers[i] if i < len(headers) else f"Objetivo {i + 1}"
        c_lbl = ws.cell(row=current_row, column=1, value=row_label)
        c_lbl.font = FONT_BODY_BOLD
        c_lbl.alignment = ALIGN_LEFT
        c_lbl.border = GRID_BORDER
        c_lbl.fill = SUBTITLE_FILL

        for j, val in enumerate(row_vals):
            cell = ws.cell(row=current_row, column=j + 2, value=val)
            cell.alignment = ALIGN_RIGHT
            cell.border = GRID_BORDER
            cell.number_format = _num_format(val, "#,##0.00##")
            if i == j:
                cell.fill = DIAGONAL_FILL
                cell.font = FONT_DIAGONAL
            else:
                cell.font = FONT_BODY
        ws.row_dimensions[current_row].height = 21
        current_row += 1

    # Ideal, Nadir, Rango de Conflicto, Fuente de normalización
    ranges = payoff.normalization_ranges or [
        abs(payoff.ideal_point[i] - payoff.anti_ideal_point[i])
        for i in range(len(headers))
    ]
    summary_specs: list[tuple[str, Sequence[Any], PatternFill, Font, str | None]] = [
        ("Punto Ideal (Z*)", payoff.ideal_point, IDEAL_FILL, FONT_IDEAL, "#,##0.00##"),
        ("Nadir aproximado (Z_peor)", payoff.anti_ideal_point, NADIR_FILL, FONT_NADIR, "#,##0.00##"),
        ("Rango de Conflicto (R_i)", ranges, RANGE_FILL, FONT_BODY_BOLD, "#,##0.00##"),
    ]
    if payoff.normalization_sources:
        source_texts = [NORM_SOURCE_LABELS.get(s, s) for s in payoff.normalization_sources]
        summary_specs.append(("Fuente de normalización", source_texts, SUBTITLE_FILL, FONT_BODY, None))

    for label, vals, fill, font, num_fmt in summary_specs:
        c_lbl = ws.cell(row=current_row, column=1, value=label)
        c_lbl.font = font
        c_lbl.fill = fill
        c_lbl.alignment = ALIGN_LEFT
        c_lbl.border = GRID_BORDER
        for j, val in enumerate(vals):
            cell = ws.cell(row=current_row, column=j + 2, value=val)
            cell.font = font
            cell.fill = fill
            cell.border = GRID_BORDER
            if num_fmt and isinstance(val, (int, float)):
                cell.alignment = ALIGN_RIGHT
                cell.number_format = _num_format(val, num_fmt)
            else:
                cell.alignment = ALIGN_CENTER
        ws.row_dimensions[current_row].height = 22
        current_row += 1

    ws.freeze_panes = "B5"
    _autofit_columns(ws, min_width=14, max_width=40, skip_merged_rows=(1, 2))


def _write_solutions_sheet(ws: Worksheet, model: ModelDefinition, result: SolveResponse) -> None:
    headers = result.payoff.headers
    var_names = [v.name for v in model.variables]
    col_headers = [
        "Métrica",
        "Estado",
        "Distancia D_p",
        *var_names,
        *[f"Z: {h}" for h in headers],
        *[f"% Logro: {h}" for h in headers],
        *[f"Desviación: {h}" for h in headers],
        *[f"Brecha ponderada: {h}" for h in headers],
    ]

    _style_banner(
        ws,
        "Soluciones de Compromiso — L1, L2 y L∞",
        "Valores óptimos de las variables de decisión, desempeño real por objetivo Z_i(x) y porcentaje de logro respecto al Punto Ideal.",
        len(col_headers),
    )

    for c_idx, h in enumerate(col_headers, start=1):
        cell = ws.cell(row=4, column=c_idx, value=h)
        cell.font = FONT_TH
        cell.fill = TABLE_HEADER_FILL
        cell.alignment = ALIGN_CENTER if c_idx <= 2 else ALIGN_RIGHT
        cell.border = HEADER_BORDER
    ws.row_dimensions[4].height = 24

    n_vars = len(var_names)
    n_objs = len(headers)
    current_row = 5
    for idx, key in enumerate(("L1", "L2", "L_inf")):
        sol = result.solutions.get(key)
        if sol is None:
            continue
        row_vals: list[Any] = [
            "L∞" if key == "L_inf" else key,
            _format_status(sol.status),
            sol.aggregate_distance if sol.objectives else None,
            *[sol.variables.get(vn) for vn in var_names],
            *[sol.objectives[i] if i < len(sol.objectives) else None for i in range(n_objs)],
            *[
                (sol.achievement_pct[i] / 100.0) if i < len(sol.achievement_pct) else None
                for i in range(n_objs)
            ],
            *[sol.normalized_distances[i] if i < len(sol.normalized_distances) else None for i in range(n_objs)],
            *[result.weights[i] * sol.normalized_distances[i]
              if i < len(sol.normalized_distances) else None for i in range(n_objs)],
        ]
        fill = ALT_ROW_FILL if idx % 2 else PatternFill(fill_type=None)
        pct_start_col = 4 + n_vars + n_objs
        z_start_col = 4 + n_vars
        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=current_row, column=c_idx, value=val)
            cell.font = FONT_BODY_BOLD if c_idx == 1 else FONT_BODY
            cell.border = GRID_BORDER
            if fill.fill_type:
                cell.fill = fill
            if c_idx <= 2:
                cell.alignment = ALIGN_CENTER
            else:
                cell.alignment = ALIGN_RIGHT
                if isinstance(val, (int, float)):
                    if pct_start_col <= c_idx < pct_start_col + n_objs:
                        cell.number_format = "0.00%"
                    elif c_idx >= z_start_col:
                        cell.number_format = _num_format(val, "#,##0.00##")
                    elif c_idx == 3:
                        cell.number_format = _num_format(val, "0.0000")
                    else:
                        cell.number_format = _num_format(val, "#,##0.####")
        ws.row_dimensions[current_row].height = 22
        current_row += 1

    ws.freeze_panes = "C5"
    _autofit_columns(ws, min_width=12, max_width=36, skip_merged_rows=(1, 2))


def _write_pareto_sheet(ws: Worksheet, model: ModelDefinition, result: SolveResponse) -> None:
    headers = result.payoff.headers
    var_names = [v.name for v in model.variables]
    col_headers = ["#", "Métrica", "Estado", *headers, *var_names]

    _style_banner(
        ws,
        "Frontera de Pareto — Puntos Eficientes Muestreados",
        "Conjunto de soluciones no dominadas generadas al variar las preferencias entre objetivos.",
        len(col_headers),
    )

    for c_idx, h in enumerate(col_headers, start=1):
        cell = ws.cell(row=4, column=c_idx, value=h)
        cell.font = FONT_TH
        cell.fill = TABLE_HEADER_FILL
        cell.alignment = ALIGN_CENTER if c_idx <= 3 else ALIGN_RIGHT
        cell.border = HEADER_BORDER
    ws.row_dimensions[4].height = 24

    for row_offset, pt in enumerate(result.pareto_points or []):
        r = 5 + row_offset
        row_vals: list[Any] = [
            row_offset + 1,
            pt.metric,
            _format_status(pt.status),
            *[pt.objectives[i] if i < len(pt.objectives) else None for i in range(len(headers))],
            *[pt.variables.get(vn) for vn in var_names],
        ]
        fill = ALT_ROW_FILL if row_offset % 2 else PatternFill(fill_type=None)
        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=r, column=c_idx, value=val)
            cell.font = FONT_BODY
            cell.border = GRID_BORDER
            if fill.fill_type:
                cell.fill = fill
            if c_idx <= 3:
                cell.alignment = ALIGN_CENTER
            else:
                cell.alignment = ALIGN_RIGHT
                if isinstance(val, (int, float)):
                    cell.number_format = _num_format(val, "#,##0.00##" if c_idx <= 3 + len(headers) else "#,##0.####")
        ws.row_dimensions[r].height = 19

    ws.freeze_panes = "A5"
    _autofit_columns(ws, min_width=10, max_width=32, skip_merged_rows=(1, 2))


def _chart_sheet_name(index: int, title: str) -> str:
    sanitized = re.sub(r"[\[\]:*?/\\'\x00-\x1f\x7f-\x9f]", " ", title)
    sanitized = " ".join(sanitized.split()) or "Gráfica"
    return f"G{index} {sanitized}"[:31].rstrip()


def build_results_workbook(
    model: ModelDefinition,
    result: SolveResponse,
    charts: Sequence[ChartImage] = (),
    warnings: Sequence[str] = (),
) -> bytes:
    """Genera el libro Excel multi-hoja estilizado con todos los resultados y la hoja Modelo re-importable."""
    wb = Workbook()

    ws_summary = wb.active
    ws_summary.title = "Resumen_Ejecutivo"
    _write_summary_sheet(ws_summary, model, result)

    ws_payoff = wb.create_sheet("Matriz_de_Pagos")
    _write_payoff_sheet(ws_payoff, result)

    ws_sols = wb.create_sheet("Soluciones_Compromiso")
    _write_solutions_sheet(ws_sols, model, result)

    if result.pareto_points:
        ws_pareto = wb.create_sheet("Frontera_Pareto")
        _write_pareto_sheet(ws_pareto, model, result)

    ws_model = wb.create_sheet("Modelo")
    _write_model_sheet(
        ws_model,
        model=model,
        weights=result.weights,
        banner_title="OptiCompromise — Definición Re-importable del Modelo",
        subtitle=None,
        extra_editable_rows=0,
    )

    if warnings:
        row = ws_summary.max_row + 2
        ws_summary.cell(row=row, column=1, value="Gráficas pendientes").font = FONT_SECTION_TITLE
        for warning in warnings:
            row += 1
            ws_summary.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
            cell = ws_summary.cell(row, 1, report_text(warning))
            cell.alignment = ALIGN_LEFT
            cell.fill = NADIR_FILL
            ws_summary.row_dimensions[row].height = 30

    for index, chart in enumerate(charts, 1):
        ws = wb.create_sheet(_chart_sheet_name(index, chart.title))
        _style_banner(ws, report_text(chart.title), report_text(chart.caption), 12)
        ws.sheet_view.showGridLines = False
        for col in range(1, 13):
            ws.column_dimensions[get_column_letter(col)].width = 12
        ws.row_dimensions[2].height = max(30, ceil(len(chart.caption) / 100) * 15)
        image = Image(BytesIO(chart.png))
        image.width = 940
        image.height = round(940 * chart.height / chart.width)
        ws.add_image(image, "A4")

    # User labels and descriptions remain text even when Excel recognizes a formula prefix.
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.data_type in {"f", "e"}:
                    cell.data_type = "s"

    return _workbook_to_bytes(wb)
