"""Printable report for a solved OptiCompromise model."""
from html import escape
from io import BytesIO
from math import isfinite
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle,
)

try:
    from .core.schemas import ModelDefinition, SolveResponse
    from .report_images import ChartImage, report_text
except ImportError:
    from core.schemas import ModelDefinition, SolveResponse
    from report_images import ChartImage, report_text


PAGE = landscape(A4)
MARGIN = 45
WIDTH = PAGE[0] - 2 * MARGIN - 12
NAVY = colors.HexColor("#15243A")
ROSE = colors.HexColor("#9F1239")
MUTED = colors.HexColor("#475569")
PALE = colors.HexColor("#F1F5F9")
RULE = colors.HexColor("#D5DFEC")
METRICS = (("L1", "L₁"), ("L2", "L₂"), ("L_inf", "L∞"))
STATUS = {
    "optimal": "Óptimo",
    "partial": "Resultado parcial",
    "feasible_suboptimal": "Factible sin certificado de optimalidad",
    "infeasible": "Infactible",
    "unbounded": "No acotado",
}

FONT_DIR = Path(__file__).with_name("fonts")
FONT_REGULAR = "OptiDejaVu"
FONT_BOLD = "OptiDejaVu-Bold"
pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))

STYLES = {
    "title": ParagraphStyle("Title", fontName=FONT_BOLD, fontSize=25, leading=29, textColor=NAVY, spaceAfter=12),
    "heading": ParagraphStyle("Heading", fontName=FONT_BOLD, fontSize=17, leading=21, textColor=NAVY, spaceBefore=12, spaceAfter=7, keepWithNext=True),
    "subheading": ParagraphStyle("Subheading", fontName=FONT_BOLD, fontSize=12, leading=15, textColor=ROSE, spaceBefore=10, spaceAfter=5, keepWithNext=True),
    "body": ParagraphStyle("Body", fontName=FONT_REGULAR, fontSize=10.5, leading=15, textColor=NAVY, spaceAfter=6),
    "caption": ParagraphStyle("Caption", fontName=FONT_REGULAR, fontSize=10, leading=14, textColor=MUTED, spaceAfter=5),
    "table": ParagraphStyle("Table", fontName=FONT_REGULAR, fontSize=9.5, leading=13, textColor=NAVY),
    "header": ParagraphStyle("Header", fontName=FONT_BOLD, fontSize=9.5, leading=13, textColor=colors.white),
}


def paragraph(text, style="body"):
    markup = escape(report_text(str(text))).replace("\n", "<br/>")
    return Paragraph(markup, STYLES[style])


def table(headers, rows, fractions):
    entries = [[paragraph(value, "header") for value in headers]]
    entries.extend([paragraph("—" if value is None else value, "table") for value in row] for row in rows)
    grid = LongTable(entries, colWidths=[WIDTH * fraction for fraction in fractions], repeatRows=1, splitInRow=1)
    grid.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return grid


def number(value):
    if value is None or not isfinite(value):
        return "—"
    return f"{value:.10g}".replace(".", ",")


def _variable_symbols(model: ModelDefinition) -> list[str]:
    heads = [
        v.name.strip().split()[0] if v.name.strip() else f"x{i}"
        for i, v in enumerate(model.variables, 1)
    ]
    counts: dict[str, int] = {}
    for head in heads:
        counts[head] = counts.get(head, 0) + 1
    return [
        v.name.strip() if counts[head] > 1 and v.name.strip() else head
        for v, head in zip(model.variables, heads)
    ]


def linear_expression(coefficients, symbols=None):
    parts = []
    for index, coefficient in enumerate(coefficients, 1):
        if coefficient == 0:
            continue
        symbol = symbols[index - 1] if symbols and index - 1 < len(symbols) else f"x{index}"
        magnitude = "" if abs(coefficient) == 1 else number(abs(coefficient)) + " · "
        term = f"{magnitude}{symbol}"
        parts.append((" − " if coefficient < 0 else " + ") + term if parts else ("−" if coefficient < 0 else "") + term)
    return "".join(parts) or "0"


def draw_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(ROSE)
    canvas.rect(MARGIN, PAGE[1] - 34, 24, 3, fill=1, stroke=0)
    canvas.setFont(FONT_BOLD, 9)
    canvas.setFillColor(NAVY)
    canvas.drawString(MARGIN + 33, PAGE[1] - 36, "OPTICOMPROMISE")
    canvas.setFont(FONT_REGULAR, 9)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE[0] - MARGIN, PAGE[1] - 36, "Introducción al Análisis de Decisiones · UNAL")
    canvas.setStrokeColor(RULE)
    canvas.line(MARGIN, 35, PAGE[0] - MARGIN, 35)
    canvas.drawString(MARGIN, 22, "Programación de compromiso multiobjetivo")
    canvas.drawRightString(PAGE[0] - MARGIN, 22, f"Página {doc.page}")
    canvas.restoreState()


def build_results_pdf(
    model: ModelDefinition, result: SolveResponse, charts: list[ChartImage], warnings: list[str],
) -> bytes:
    out = BytesIO()
    document = SimpleDocTemplate(
        out, pagesize=PAGE, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=56, bottomMargin=47,
        title=model.name or "Reporte de optimización", author="OptiCompromise",
    )
    story = [
        paragraph("Reporte de optimización", "subheading"),
        paragraph(model.name or "Modelo sin título", "title"),
        paragraph(f"{len(model.variables)} variables · {len(model.objectives)} objetivos · {len(model.constraints)} restricciones", "caption"),
    ]
    if model.description:
        story.append(paragraph(model.description))
    if model.reference:
        story.append(paragraph(f"Fuente académica · {model.reference}", "caption"))

    symbols = _variable_symbols(model)
    def _var_bounds(variable):
        if variable.var_type == "binary":
            lb = 0.0 if variable.lower_bound is None else variable.lower_bound
            ub = 1.0 if variable.upper_bound is None else variable.upper_bound
            return number(lb), number(ub)
        return (
            "−∞" if variable.lower_bound is None else number(variable.lower_bound),
            "+∞" if variable.upper_bound is None else number(variable.upper_bound),
        )

    story += [
        paragraph("Formulación matemática", "heading"),
        table(["Símbolo", "Variable", "Tipo", "Cota inferior", "Cota superior"], (
            (symbol, variable.name, {"continuous": "Continua", "integer": "Entera", "binary": "Binaria"}[variable.var_type],
             *_var_bounds(variable))
            for symbol, variable in zip(symbols, model.variables)
        ), [.14, .39, .15, .16, .16]),
        paragraph("Objetivos y ponderaciones", "subheading"),
        table(["Objetivo", "Expresión lineal", "Sentido", "Peso"], (
            (f"Z{i + 1} · {objective.name}", linear_expression(objective.coefficients, symbols),
             "Maximizar" if objective.sense == "maximize" else "Minimizar", number(result.weights[i]))
            for i, objective in enumerate(model.objectives)
        ), [.29, .46, .13, .12]),
    ]
    if model.constraints:
        story += [
            paragraph("Restricciones", "subheading"),
            table(["Restricción", "Expresión"], (
                (constraint.name, f"{linear_expression(constraint.coefficients, symbols)} {constraint.sense.replace('==', '=')} {number(constraint.rhs)}")
                for constraint in model.constraints
            ), [.30, .70]),
        ]

    payoff = result.payoff
    n_objs = max(len(payoff.headers), 1)
    payoff_col_frac = round((1.0 - 0.24) / n_objs, 4)
    payoff_fracs = [1.0 - payoff_col_frac * n_objs, *([payoff_col_frac] * n_objs)]
    norm_ranges = payoff.normalization_ranges or [
        abs(payoff.ideal_point[i] - payoff.anti_ideal_point[i]) for i in range(len(payoff.headers))
    ]
    norm_labels = {
        "payoff": "Matriz de pagos",
        "feasible_range": "Rango factible",
        "constant": "Constante",
        "unit": "Unitaria",
    }
    payoff_rows = [
        *[
            (f"Z{i + 1} · {payoff.headers[i]}", *[number(val) for val in row])
            for i, row in enumerate(payoff.matrix)
        ],
        ("Punto Ideal (Z*)", *[number(val) for val in payoff.ideal_point]),
        ("Nadir aproximado", *[number(val) for val in payoff.anti_ideal_point]),
        ("Rango (Rᵢ)", *[number(val) for val in norm_ranges]),
    ]
    if payoff.normalization_sources:
        payoff_rows.append(("Base de escala", *[norm_labels.get(s, s) for s in payoff.normalization_sources]))

    metrics = [(key, label, result.solutions.get(key)) for key, label in METRICS]
    story += [
        PageBreak(),
        paragraph("Matriz de pagos y referencias", "heading"),
        paragraph("Cada fila evalúa todos los objetivos en el óptimo individual del criterio indicado. El peor valor por columna define el nadir aproximado.", "caption"),
        table(["Objetivo optimizado", *[f"Z{i + 1} · {h}" for i, h in enumerate(payoff.headers)]], payoff_rows, payoff_fracs),
        paragraph("Resultados de compromiso", "heading"),
        paragraph(f"Estado del cálculo · {STATUS.get(result.status, result.status)}"),
        paragraph(result.message, "caption"),
        table(["Métrica", "Estado", "Distancia", "Criterio que minimiza"], (
            (label, STATUS.get(solution.status, solution.status) if solution else "Sin solución",
             number(solution.aggregate_distance) if solution and solution.objectives else None,
             criterion_text)
            for (_, label, solution), criterion_text in zip(metrics, (
                "Suma de las brechas ponderadas.",
                "Raíz de la suma de los cuadrados de las brechas ponderadas.",
                "Mayor brecha ponderada (minimax).",
            ))
        ), [.10, .28, .14, .48]),
        paragraph("Decisiones por métrica", "subheading"),
        table(["Variable", *[label for _, label, _ in metrics]], (
            (variable.name, *[
                number(solution.variables.get(variable.name)) if solution else "—"
                for _, _, solution in metrics
            ])
            for variable in model.variables
        ), [.40, .20, .20, .20]),
        PageBreak(),
        paragraph("Comparación por objetivo", "heading"),
        paragraph("Valores y desviaciones por objetivo", "subheading"),
        paragraph("La desviación normalizada mide la brecha al ideal. La brecha ponderada multiplica esa desviación por el peso del objetivo. Un logro de 100 % corresponde al ideal.", "caption"),
    ]

    def objective_rows():
        for i, objective in enumerate(model.objectives):
            for _, label, solution in metrics:
                has_value = solution is not None and i < len(solution.objectives)
                deviation = solution.normalized_distances[i] if solution and i < len(solution.normalized_distances) else None
                achievement = solution.achievement_pct[i] if solution and i < len(solution.achievement_pct) else None
                yield (
                    f"Z{i + 1} · {objective.name}", label, number(solution.objectives[i]) if has_value else None,
                    number(payoff.ideal_point[i]), number(payoff.anti_ideal_point[i]), number(deviation),
                    number(result.weights[i] * deviation) if deviation is not None else None,
                    number(achievement) + " %" if achievement is not None else None,
                )

    story += [
        table(["Objetivo", "Métrica", "Valor", "Ideal", "Nadir aprox.", "Desviación", "Brecha ponderada", "Logro"], objective_rows(),
              [.24, .08, .12, .11, .11, .11, .12, .11]),
    ]
    if warnings:
        story.append(paragraph("Gráficas pendientes", "subheading"))
        story.extend(paragraph(warning, "caption") for warning in warnings)

    for chart in charts:
        scale = min(WIDTH / chart.width, 395 / chart.height)
        image = Image(BytesIO(chart.png), width=chart.width * scale, height=chart.height * scale)
        image.hAlign = "CENTER"
        story += [
            PageBreak(),
            paragraph(chart.title, "heading"),
            image,
            Spacer(1, 4),
            paragraph(chart.caption, "caption"),
        ]

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return out.getvalue()
