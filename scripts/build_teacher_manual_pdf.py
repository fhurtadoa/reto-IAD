"""
Generador del Manual Docente para Carga, Personalización y Revisión de Ejercicios
en OptiCompromise (Opción 4 - IAD UNAL).
Genera web/public/MANUAL_DOCENTE_OPTICOMPROMISE.pdf.
"""
import os
import shutil
import matplotlib

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# 1. REGISTRO DE FUENTES UNICODE (DejaVu Sans / Mono)
# =============================================================================
TTF_DIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(TTF_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(TTF_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Italic", os.path.join(TTF_DIR, "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFont(
    TTFont("DejaVu-BoldItalic", os.path.join(TTF_DIR, "DejaVuSans-BoldOblique.ttf"))
    if os.path.exists(os.path.join(TTF_DIR, "DejaVuSans-BoldOblique.ttf"))
    else TTFont("DejaVu-BoldItalic", os.path.join(TTF_DIR, "DejaVuSans-Bold.ttf"))
)
registerFontFamily(
    "DejaVu",
    normal="DejaVu",
    bold="DejaVu-Bold",
    italic="DejaVu-Italic",
    boldItalic="DejaVu-BoldItalic",
)

pdfmetrics.registerFont(TTFont("DejaVuMono", os.path.join(TTF_DIR, "DejaVuSansMono.ttf")))
pdfmetrics.registerFont(TTFont("DejaVuMono-Bold", os.path.join(TTF_DIR, "DejaVuSansMono-Bold.ttf")))
registerFontFamily(
    "DejaVuMono",
    normal="DejaVuMono",
    bold="DejaVuMono-Bold",
    italic="DejaVuMono",
    boldItalic="DejaVuMono-Bold",
)


# =============================================================================
# 2. DECORACIÓN DE PÁGINAS DEL PDF (Misma estética editorial UNAL)
# =============================================================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            return
        self.saveState()
        self.setFont("DejaVu", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(48, 754, "OptiCompromise — Guía Docente de Carga de Ejercicios | IAD UNAL")
        self.drawRightString(612 - 48, 754, "Opción 4: Programación de Compromiso")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(48, 748, 612 - 48, 748)
        self.line(48, 44, 612 - 48, 44)
        self.drawString(48, 33, "Facultad de Minas — Universidad Nacional de Colombia (Sede Medellín)")
        self.drawRightString(612 - 48, 33, f"Página {self._pageNumber} de {page_count}")
        self.restoreState()


def _callout_box(html_text: str, bg_hex: str, border_hex: str, box_style: ParagraphStyle):
    return Table(
        [[Paragraph(html_text, box_style)]],
        colWidths=[516],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg_hex)),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(border_hex)),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]),
    )


def build_teacher_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=48,
        rightMargin=48,
        topMargin=54,
        bottomMargin=52,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TTitle", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=18.5, leading=24,
        textColor=colors.HexColor("#0F172A"), spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "TSub", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=10.5, leading=14,
        textColor=colors.HexColor("#E11D48"), spaceAfter=10,
    )
    h1_style = ParagraphStyle(
        "TH1", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=13, leading=17,
        textColor=colors.HexColor("#0F172A"), spaceBefore=8, spaceAfter=4, keepWithNext=True,
    )
    h2_style = ParagraphStyle(
        "TH2", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=10.2, leading=13.5,
        textColor=colors.HexColor("#E11D48"), spaceBefore=7, spaceAfter=3, keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "TBody", parent=styles["Normal"], fontName="DejaVu", fontSize=8.7, leading=12.8,
        textColor=colors.HexColor("#1E293B"), spaceAfter=5,
    )
    bullet_style = ParagraphStyle(
        "TBullet", parent=styles["Normal"], fontName="DejaVu", fontSize=8.4, leading=12.2,
        textColor=colors.HexColor("#1E293B"), leftIndent=12, spaceAfter=3.5,
    )
    th_style = ParagraphStyle(
        "TTH", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=7.6, leading=10,
        textColor=colors.white, alignment=1,
    )
    td_style = ParagraphStyle(
        "TTD", parent=styles["Normal"], fontName="DejaVu", fontSize=7.6, leading=10.2,
        textColor=colors.HexColor("#0F172A"),
    )
    td_bold = ParagraphStyle(
        "TTDB", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=7.6, leading=10.2,
        textColor=colors.HexColor("#0F172A"),
    )
    code_style = ParagraphStyle(
        "TCode", parent=styles["Normal"], fontName="DejaVuMono", fontSize=7.4, leading=10.5,
        textColor=colors.HexColor("#0F172A"),
    )
    box_style = ParagraphStyle(
        "TBox", parent=styles["Normal"], fontName="DejaVu", fontSize=8.2, leading=12,
        textColor=colors.HexColor("#0F172A"),
    )

    tbl_style_dark = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111524")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ])

    story = []

    # =========================================================================
    # PORTADA / PÁGINA 1: RESUMEN EJECUTIVO Y ALCANCE PARA DOCENTES
    # =========================================================================
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "UNIVERSIDAD NACIONAL DE COLOMBIA — FACULTAD DE MINAS",
        ParagraphStyle("UH", fontName="DejaVu-Bold", fontSize=9.2, leading=12, textColor=colors.HexColor("#E11D48")),
    ))
    story.append(Paragraph(
        "INTRODUCCIÓN AL ANÁLISIS DE DECISIONES (IAD) | GUÍA PRÁCTICA PARA DOCENTES Y MONITORES",
        ParagraphStyle("DH", fontName="DejaVu", fontSize=8, leading=11, textColor=colors.HexColor("#64748B"), spaceAfter=10),
    ))
    story.append(HRFlowable(width="100%", thickness=2.2, color=colors.HexColor("#E11D48"), spaceAfter=12))

    story.append(Paragraph("Manual del Docente — OptiCompromise", title_style))
    story.append(Paragraph("Carga de Ejercicios, Personalización de Talleres y Lectura de Reportes Excel", subtitle_style))
    story.append(Paragraph(
        "Documento operativo para preparar casos de clase, talleres parametrizados por estudiante (ej. Taller 1 y Taller 3 de "
        "<i>Producción de Papel</i>), evaluaciones en <b>OptiCompromise</b> y revisión de libros de resultados sin escribir código.",
        body_style,
    ))

    meta_rows = [
        [Paragraph("<b>Dirigido a</b>", td_bold), Paragraph("Docentes y monitores de Introducción al Análisis de Decisiones (IAD — UNAL Medellín)", td_style)],
        [Paragraph("<b>Plantilla oficial</b>", td_bold), Paragraph("<font face='DejaVuMono'>plantilla-ejercicio-iad.xlsx</font>, con un ejemplo de Producción de Papel en una hoja de consulta.", td_style)],
        [Paragraph("<b>Acceso en la interfaz</b>", td_bold), Paragraph("<b>Formular</b> incluye <b>Obtener plantilla (.xlsx)</b>, <b>Cargar ejercicio</b> (<font face='DejaVuMono'>.xlsx/.csv/.json</font>), <b>Nuevo modelo</b> y <b>Guardar (.json)</b>. El pie incluye <b>Ejemplos</b>; <b>Explorar resultados</b> reúne Copiar, Excel y PDF.", td_style)],
        [Paragraph("<b>Soporte de Modelos</b>", td_bold), Paragraph("Lineales continuos (ℝ) y Enteros Mixtos MIP (ℤ, {0,1}), ≥2 o ≥3 objetivos (<font face='DejaVuMono'>maximize</font> / <font face='DejaVuMono'>minimize</font>)", td_style)],
    ]
    t_meta = Table(meta_rows, colWidths=[122, 394])
    t_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Mapa de Rutas de Trabajo para el Profesor", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E11D48"), spaceAfter=6))

    routes_rows = [
        [Paragraph("<b>Ruta</b>", th_style), Paragraph("<b>Cuándo usarla</b>", th_style), Paragraph("<b>Artefacto / Acción clave</b>", th_style)],
        [
            Paragraph("<b>Ruta 1 · Plantilla Excel (.xlsx)</b>", td_bold),
            Paragraph("Preparar talleres grandes (≥4 variables), variantes por estudiante o distribuir enunciados listos en Moodle.", td_style),
            Paragraph("Diligenciar la hoja <font face='DejaVuMono'>Modelo</font> de la plantilla oficial y abrir con <b>Cargar ejercicio</b>.", td_style),
        ],
        [
            Paragraph("<b>Ruta 2 · Modo Algebraico (Texto)</b>", td_bold),
            Paragraph("Formular un ejercicio rápido en vivo frente al grupo copiando ecuaciones del tablero.", td_style),
            Paragraph("Pegar <font face='DejaVuMono'>Max Z1 = ...</font>, <font face='DejaVuMono'>s.a.</font> y pulsar <b>Aplicar Ecuaciones y Resolver</b>.", td_style),
        ],
        [
            Paragraph("<b>Ruta 3 · Carpeta ejercicios/ y Reabrir</b>", td_bold),
            Paragraph("Distribuir los casos del semestre en Excel o calificar entregas descargadas de estudiantes.", td_style),
            Paragraph("Usar el botón <b>Ejemplos</b> del pie de página, los libros <font face='DejaVuMono'>ejercicios/*.xlsx</font>, o reabrir <font face='DejaVuMono'>.xlsx/.json/.csv</font> de estudiantes con <b>Cargar ejercicio</b>.", td_style),
        ],
        [
            Paragraph("<b>Ruta 4 · Excel y PDF de resultados</b>", td_bold),
            Paragraph("Revisar matriz de pagos, logros, variables, frontera Pareto y auditar lo que formuló el estudiante.", td_style),
            Paragraph("Descargar Excel o PDF con las gráficas aplicables. Excel incluye una hoja <font face='DejaVuMono'>Modelo</font> reutilizable.", td_style),
        ],
    ]
    t_routes = Table(routes_rows, colWidths=[125, 195, 196])
    t_routes.setStyle(tbl_style_dark)
    story.append(t_routes)
    story.append(Spacer(1, 10))

    story.append(_callout_box(
        "<b>Alcance del motor (qué sí y qué no importar):</b> OptiCompromise resuelve modelos <b>lineales continuos y enteros mixtos (MIP)</b> "
        "deterministas con 2 o más objetivos. <b>No admite</b> términos cuadráticos o productos entre variables (<font face='DejaVuMono'>x1*x2</font>), "
        "divisiones por variables, simulación estocástica, árboles de decisión ni matrices de comparaciones pareadas AHP o matrices finitas discretas. "
        "Recuerda que <b>Sensibilidad de pesos</b> se habilita con exactamente 2 objetivos, y <b>Región Factible</b> con exactamente 2 variables.",
        "#FFF1F2", "#E11D48", box_style,
    ))

    story.append(PageBreak())

    # =========================================================================
    # Plantilla oficial de carga
    story.append(Paragraph("1. Preparar un ejercicio en Excel", h1_style))
    story.append(Paragraph(
        "En <b>Formular</b>, pulsa <b>Obtener plantilla (.xlsx)</b>. Diligencia <b>Modelo</b>, guarda el libro y pulsa "
        "<b>Cargar ejercicio</b>. La hoja <b>Ejemplo_Papel</b> contiene un ejemplo de consulta. "
        "El importador lee únicamente la hoja <b>Modelo</b>.",
        body_style,
    ))

    story.append(Paragraph("1.1 Hojas del libro plantilla (.xlsx)", h2_style))
    story.append(Paragraph(
        "• <b>Hoja <font face='DejaVuMono'>Modelo</font>:</b> Contiene la tabla estructurada que lee OptiCompromise al pulsar <b>Cargar ejercicio</b>.<br/>"
        "• <b>Hoja <font face='DejaVuMono'>Guia_Docente</font>:</b> Hoja informativa con el diccionario de columnas y valores permitidos para consulta rápida dentro de Excel; es ignorada por el importador.",
        bullet_style,
    ))

    story.append(Paragraph("1.2 Estructura exacta de columnas y filas en la hoja Modelo", h2_style))
    story.append(Paragraph(
        "Las <b>5 primeras columnas</b> definen la estructura fija del modelo y deben conservar su encabezado exacto; a partir de la columna 6 se agrega <b>una columna por cada variable de decisión</b>:",
        body_style,
    ))
    story.append(Paragraph(
        "<font face='DejaVuMono'><b>Seccion</b> | <b>Nombre</b> | <b>Tipo_o_Sentido</b> | <b>Min_o_RHS</b> | <b>Max_o_Peso</b> | &lt;var_1&gt; | &lt;var_2&gt; | ...</font>",
        ParagraphStyle("MonoLine", fontName="DejaVuMono", fontSize=7.8, leading=11, backColor=colors.HexColor("#F1F5F9"), borderPadding=5, spaceAfter=6),
    ))

    schema_rows = [
        [
            Paragraph("<b>Seccion</b>", th_style),
            Paragraph("<b>Nombre</b>", th_style),
            Paragraph("<b>Tipo_o_Sentido</b>", th_style),
            Paragraph("<b>Min_o_RHS</b>", th_style),
            Paragraph("<b>Max_o_Peso</b>", th_style),
            Paragraph("<b>Cols. de Variables</b>", th_style),
        ],
        [
            Paragraph("<b>Meta</b><br/><i>(1 fila)</i>", td_bold),
            Paragraph("Título del ejercicio", td_style),
            Paragraph("Enunciado, contexto y unidades", td_style),
            Paragraph("Semilla Pareto opcional con ≥4 Z (ej. <font face='DejaVuMono'>42</font>)", td_style),
            Paragraph("Fuente académica (ej. <i>IAD Taller 3</i>)", td_style),
            Paragraph("Vacías", td_style),
        ],
        [
            Paragraph("<b>Variable</b><br/><i>(1 por var.)</i>", td_bold),
            Paragraph("Identificador único (igual a su columna)", td_style),
            Paragraph("<font face='DejaVuMono'>continuous</font>, <font face='DejaVuMono'>integer</font> o <font face='DejaVuMono'>binary</font>", td_style),
            Paragraph("Cota inferior. Vacío = <font face='DejaVuMono'>0</font>. Sin límite = <font face='DejaVuMono'>-inf</font>", td_style),
            Paragraph("Cota sup. Vacío = <font face='DejaVuMono'>+inf</font> (o <font face='DejaVuMono'>1</font> si binaria; fija <font face='DejaVuMono'>[1,1]</font>)", td_style),
            Paragraph("Vacías", td_style),
        ],
        [
            Paragraph("<b>Objetivo</b><br/><i>(≥2 filas)</i>", td_bold),
            Paragraph("Nombre y unidad del criterio", td_style),
            Paragraph("<font face='DejaVuMono'>maximize</font> o <font face='DejaVuMono'>minimize</font>", td_style),
            Paragraph("Vacío", td_style),
            Paragraph("Peso ∈ [0,1]. Todos llenos (Σ=1.0) o <b>todos vacíos</b> (= pesos iguales)", td_style),
            Paragraph("Coeficiente numérico (vacío = <font face='DejaVuMono'>0</font>)", td_style),
        ],
        [
            Paragraph("<b>Restriccion</b><br/><i>(0 o más)</i>", td_bold),
            Paragraph("Nombre de la restricción", td_style),
            Paragraph("<font face='DejaVuMono'>&lt;=</font>, <font face='DejaVuMono'>&gt;=</font> o <font face='DejaVuMono'>==</font> (o <font face='DejaVuMono'>'= </font>)", td_style),
            Paragraph("Valor numérico del lado derecho (RHS)", td_style),
            Paragraph("Vacío", td_style),
            Paragraph("Coeficiente numérico (vacío = <font face='DejaVuMono'>0</font>)", td_style),
        ],
    ]
    t_schema = Table(schema_rows, colWidths=[64, 84, 98, 92, 96, 82])
    t_schema.setStyle(tbl_style_dark)
    story.append(t_schema)
    story.append(Spacer(1, 6))

    story.append(Paragraph("1.3 Valores válidos y alias aceptados por el importador", h2_style))
    story.append(Paragraph(
        "• <b>Tipo de variable:</b> <font face='DejaVuMono'>continuous</font> (<font face='DejaVuMono'>continua</font>), "
        "<font face='DejaVuMono'>integer</font> (<font face='DejaVuMono'>entera</font>), "
        "<font face='DejaVuMono'>binary</font> (<font face='DejaVuMono'>binaria</font>).<br/>"
        "• <b>Sentido de objetivo:</b> <font face='DejaVuMono'>maximize</font> (<font face='DejaVuMono'>max</font>, <font face='DejaVuMono'>maximizar</font>) "
        "o <font face='DejaVuMono'>minimize</font> (<font face='DejaVuMono'>min</font>, <font face='DejaVuMono'>minimizar</font>).<br/>"
        "• <b>Operadores de restricción:</b> <font face='DejaVuMono'>&lt;=</font> (<font face='DejaVuMono'>≤</font>), "
        "<font face='DejaVuMono'>&gt;=</font> (<font face='DejaVuMono'>≥</font>), <font face='DejaVuMono'>==</font> (<font face='DejaVuMono'>=</font>). "
        "<i>En Excel usa <font face='DejaVuMono'>==</font> o <font face='DejaVuMono'>'= </font> para evitar que Excel interprete una fórmula.</i><br/>"
        "• <b>Cotas infinitas y binarias:</b> Acepta <font face='DejaVuMono'>-inf</font>, <font face='DejaVuMono'>+inf</font>, <font face='DejaVuMono'>inf</font>, "
        "<font face='DejaVuMono'>-∞</font>, <font face='DejaVuMono'>+∞</font>. En variables binarias puedes dejar <font face='DejaVuMono'>[0, 1]</font> o fijar <font face='DejaVuMono'>[1, 1]</font> / <font face='DejaVuMono'>[0, 0]</font>.<br/>"
        "• <b>Pesos (<font face='DejaVuMono'>Max_o_Peso</font>):</b> O se dejan <b>todos vacíos</b> (pesos iguales <i>1/q</i>), o se completan todos con suma igual a <b>1.00</b> (±0.001).",
        bullet_style,
    ))

    story.append(PageBreak())

    # =========================================================================
    # PERSONALIZACIÓN DE VARIANTES + QUÉ NO HACER
    # =========================================================================
    story.append(Paragraph("1.4 Personalizar variantes por estudiante (Taller 3: Producción de Papel)", h2_style))
    story.append(Paragraph(
        "La hoja <font face='DejaVuMono'>Ejemplo_Papel</font> incluye las 12 variables (<font face='DejaVuMono'>x1_1 (M1 Prensa)</font> … "
        "<font face='DejaVuMono'>x3_4 (M3 Reciclado)</font>), los costos unitarios, los indicadores de calidad, las horas disponibles (5 h, 3 h, 3 h) "
        "y las tasas convertidas a horas por tonelada (<font face='DejaVuMono'>1/tasa</font>). Para generar la variante del Taller 3 con dígito <b>n</b>:",
        body_style,
    ))
    story.append(Paragraph(
        "1. Copia a <font face='DejaVuMono'>Modelo</font> los datos de <font face='DejaVuMono'>Ejemplo_Papel</font> que vayas a adaptar.<br/>"
        "2. En la fila <b>Restriccion</b> → <font face='DejaVuMono'>Demanda mínima · Prensa</font>, reemplaza <font face='DejaVuMono'>Min_o_RHS</font> = <font face='DejaVuMono'>77</font> por <b><font face='DejaVuMono'>77 + n</font></b> (por ejemplo, para <font face='DejaVuMono'>n = 6</font>, ingresa <font face='DejaVuMono'>83</font>).<br/>"
        "3. En las dos filas <b>Objetivo</b>, ajusta la columna <font face='DejaVuMono'>Max_o_Peso</font>: Costo = <b><font face='DejaVuMono'>0.5 + 0.01·n</font></b> (<font face='DejaVuMono'>0.56</font> si n=6) y Calidad = <b><font face='DejaVuMono'>0.5 − 0.01·n</font></b> (<font face='DejaVuMono'>0.44</font> si n=6).<br/>"
        "4. Actualiza el título en <b>Meta</b> usando únicamente el dígito <font face='DejaVuMono'>n</font> (sin guardar cédulas ni documentos completos) e impórtalo en OptiCompromise.",
        bullet_style,
    ))

    story.append(Spacer(1, 4))
    story.append(Paragraph("1.5 Qué NO hacer al editar plantillas (errores comunes)", h2_style))
    dont_rows = [
        [Paragraph("<b>Error común</b>", th_style), Paragraph("<b>Por qué falla</b>", th_style), Paragraph("<b>Cómo corregirlo</b>", th_style)],
        [
            Paragraph("Usar nombres reservados de columna como variable (ej. <font face='DejaVuMono'>Seccion</font>, <font face='DejaVuMono'>Nombre</font>, <font face='DejaVuMono'>Min</font>, <font face='DejaVuMono'>Max</font>, <font face='DejaVuMono'>Peso</font>, <font face='DejaVuMono'>RHS</font>)", td_style),
            Paragraph("Colisionan con las columnas fijas de metadatos durante la lectura tabular.", td_style),
            Paragraph("Usa nombres como <font face='DejaVuMono'>x1</font>, <font face='DejaVuMono'>y_planta</font>; o escribe el encabezado de coeficientes con prefijo <font face='DejaVuMono'>Coef: Max</font>.", td_style),
        ],
        [
            Paragraph("Escribir expresiones no lineales (<font face='DejaVuMono'>x1*x2</font>, <font face='DejaVuMono'>x1^2</font>) o texto en coeficientes", td_style),
            Paragraph("El motor es lineal/MIP y las celdas de coeficientes solo aceptan números finitos.", td_style),
            Paragraph("Ingresa el número real calculado (ej. <font face='DejaVuMono'>0.018868</font> en vez de texto <font face='DejaVuMono'>1/53</font> en Excel).", td_style),
        ],
        [
            Paragraph("Mezclar pesos vacíos y numéricos o que no sumen 1.00", td_style),
            Paragraph("La validación exige vector completo con Σw = 1.00 (±0.001) o todos vacíos.", td_style),
            Paragraph("Completa todos los pesos o deja toda la columna <font face='DejaVuMono'>Max_o_Peso</font> vacía en los objetivos.", td_style),
        ],
        [
            Paragraph("Agregar una fila <font face='DejaVuMono'>Restriccion</font> incompleta o escribir <font face='DejaVuMono'>=</font> sin apóstrofe en Excel", td_style),
            Paragraph("Excel interpreta <font face='DejaVuMono'>=</font> como fórmula rota (<font face='DejaVuMono'>#NOMBRE?</font>) o falta el valor RHS.", td_style),
            Paragraph("Elimina las filas de restricción que no uses y escribe <font face='DejaVuMono'>==</font> o <font face='DejaVuMono'>'= </font> para igualdades.", td_style),
        ],
    ]
    t_dont = Table(dont_rows, colWidths=[172, 166, 178])
    t_dont.setStyle(tbl_style_dark)
    story.append(t_dont)
    story.append(Spacer(1, 10))

    # =========================================================================
    # RUTA 2: CARGA RÁPIDA POR TEXTO EN MODO ALGEBRAICO
    # =========================================================================
    story.append(Paragraph("2. Ruta 2: Carga rápida por texto en Modo Algebraico", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E11D48"), spaceAfter=6))
    story.append(Paragraph(
        "Para formular un ejercicio en vivo durante la clase sin abrir Excel, usa el editor de texto en <b>Formular → Modo Algebraico</b>:",
        body_style,
    ))
    story.append(Paragraph(
        "1. En <b>Formular</b> pulsa <b>Nuevo modelo</b> y cambia a la pestaña <b>Modo Algebraico</b>.<br/>"
        "2. Escribe o pega los objetivos (<font face='DejaVuMono'>Max</font>/<font face='DejaVuMono'>Min</font>), la línea separadora <font face='DejaVuMono'>s.a.</font> y las restricciones lineales:<br/>"
        "<font face='DejaVuMono'>   Max Z1 (Utilidad USD) = 1000*x1 + 3000*x2<br/>"
        "   Min Z2 (Contaminacion kg) = x1 + 2*x2<br/>"
        "   s.a.<br/>"
        "   x1 + x2 &lt;= 400<br/>"
        "   1000*x1 + 3000*x2 &gt;= 300000</font><br/>"
        "3. Pulsa <b>Aplicar Ecuaciones y Resolver</b>. <i>Importante: mientras haya cambios sin aplicar aparece el estado <b>Borrador sin aplicar</b> y se bloquean el cambio a Ver método / Explorar resultados.</i><br/>"
        "4. Si el ejercicio tiene variables enteras (<font face='DejaVuMono'>ℤ</font>), binarias (<font face='DejaVuMono'>{0,1}</font>) o cotas diferentes de <font face='DejaVuMono'>[0, +inf)</font>, cambia a <b>Modo Tabla</b> para ajustarlas junto con el título y la descripción.<br/>"
        "5. Pulsa <b>Guardar (.json)</b> para conservar la formulación actual, o descarga el Excel de resultados para reabrir el modelo desde <b>Formular</b>.",
        bullet_style,
    ))
    story.append(Spacer(1, 4))
    story.append(_callout_box(
        "<b>Capacidades del parser algebraico:</b> Soporta operadores <font face='DejaVuMono'>&lt;=</font>, <font face='DejaVuMono'>&gt;=</font>, "
        "<font face='DejaVuMono'>=</font>, <font face='DejaVuMono'>==</font>, símbolos Unicode (<font face='DejaVuMono'>≤, ≥, −</font>), comas decimales "
        "(<font face='DejaVuMono'>2,5</font>), comentarios (<font face='DejaVuMono'>#</font> o <font face='DejaVuMono'>//</font>) y variables o constantes en ambos lados de una restricción "
        "(ej. <font face='DejaVuMono'>x1 &lt;= 2*x2 + 10</font>). Los objetivos no deben incluir términos independientes constantes.",
        "#F8FAFC", "#CBD5E1", box_style,
    ))

    story.append(PageBreak())

    # =========================================================================
    # RUTA 3: CATÁLOGO COMPARTIDO Y REAPERTURA DE LIBROS
    # =========================================================================
    story.append(Paragraph("3. Ruta 3: Publicar en el catálogo compartido o reabrir entregas", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E11D48"), spaceAfter=6))

    story.append(Paragraph("3.1 Incorporar un ejercicio a la carpeta compartida", h2_style))
    story.append(Paragraph(
        "• <b>Carpeta ejercicios/:</b> Comparte el libro <font face='DejaVuMono'>.xlsx</font> terminado o añade su definición JSON en <font face='DejaVuMono'>examples/</font> y ejecuta <font face='DejaVuMono'>python3 scripts/build_excel_templates.py</font> para regenerar <font face='DejaVuMono'>ejercicios/*.xlsx</font>.<br/>"
        "• <b>Prueba inmediata:</b> Abre cualquier archivo generado mediante <b>Formular → Cargar ejercicio</b> y verifica que se resuelva correctamente.",
        bullet_style,
    ))

    story.append(Paragraph("3.2 Reabrir libros Excel de resultados", h2_style))
    story.append(Paragraph(
        "Cada Excel de resultados incluye una hoja <font face='DejaVuMono'>Modelo</font> con las variables, cotas, objetivos, restricciones y pesos usados. Para revisar el ejercicio, pulsa <b>Cargar ejercicio</b> en <b>Formular</b> y selecciona el libro.",
        body_style,
    ))
    story.append(Spacer(1, 6))

    # =========================================================================
    # Resultados en Excel y PDF
    # =========================================================================
    story.append(Paragraph("4. Uso e interpretación de resultados", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E11D48"), spaceAfter=6))
    story.append(Paragraph(
        "Al pulsar <b>Excel</b> en <b>Explorar resultados</b>, OptiCompromise descarga un libro <font face='DejaVuMono'>.xlsx</font> estilizado con hojas de datos para auditoría y una hoja por gráfica aplicable.",
        body_style,
    ))

    sheets_rows = [
        [Paragraph("<b>Hoja del libro .xlsx</b>", th_style), Paragraph("<b>Contenido principal</b>", th_style), Paragraph("<b>Qué revisar como docente / monitor</b>", th_style)],
        [
            Paragraph("<b>1. Resumen_Ejecutivo</b>", td_bold),
            Paragraph("Metadatos del modelo, dimensiones, vector de pesos aplicado, estado del solver y resumen Ideal / Nadir / métricas.", td_style),
            Paragraph("Verificar que el estudiante usó los pesos asignados (<font face='DejaVuMono'>Σw = 1</font>) y que el estado sea <font face='DejaVuMono'>optimal</font> (o revisar aviso si es <font face='DejaVuMono'>partial</font> en L₂ MIP).", td_style),
        ],
        [
            Paragraph("<b>2. Matriz_de_Pagos</b>", td_bold),
            Paragraph("Tabla cuadrada <font face='DejaVuMono'>q × q</font> con el desempeño de cada criterio en los óptimos individuales, fila Ideal (<font face='DejaVuMono'>Z*</font>), Nadir aproximado y rangos de normalización.", td_style),
            Paragraph("Comprobar contra la solución manual del taller que los extremos individuales coinciden y el conflicto entre criterios está bien formulado.", td_style),
        ],
        [
            Paragraph("<b>3. Soluciones_Compromiso</b>", td_bold),
            Paragraph("Comparativa completa de <b>L₁</b>, <b>L₂</b> y <b>L∞</b>: estado, distancia agregada <font face='DejaVuMono'>D_p</font> (<font face='DejaVuMono'>λ*</font> en L∞), vector <font face='DejaVuMono'>x*</font>, valores reales <font face='DejaVuMono'>Z_i(x*)</font> y <b>% de logro</b>.", td_style),
            Paragraph("Evaluar el vector de decisiones <font face='DejaVuMono'>x*</font>, validar el equilibrio de logros en L∞ frente a la compensación de L₁ y comparar con las tablas de clase.", td_style),
        ],
        [
            Paragraph("<b>4. Frontera_Pareto</b><br/><i>(si aplica)</i>", td_bold),
            Paragraph("Muestra de soluciones no dominadas obtenidas por barrido de pesos sobre L₁, L₂ y L∞ (pesos, estado, objetivos y variables).", td_style),
            Paragraph("Analizar la forma de la frontera (continua vs discreta en MIP) o graficar compensaciones en talleres avanzados.", td_style),
        ],
        [
            Paragraph("<b>5. Modelo</b><br/><i>(100% re-importable)</i>", td_bold),
            Paragraph("Tabla estándar <font face='DejaVuMono'>Meta / Variable / Objetivo / Restriccion</font> idéntica a la plantilla de carga.", td_style),
            Paragraph("Auditar coeficientes, sentidos y cotas ingresados; re-importar el mismo archivo en OptiCompromise para probar otra sensibilidad.", td_style),
        ],
    ]
    t_sheets = Table(sheets_rows, colWidths=[118, 200, 198])
    t_sheets.setStyle(tbl_style_dark)
    story.append(t_sheets)
    story.append(Spacer(1, 8))

    story.append(_callout_box(
        "<b>PDF (.pdf)</b> presenta la formulación, las tablas de resultados, la interpretación y las gráficas. "
        "Ambos documentos incluyen las vistas aplicables al modelo aunque su pestaña no se haya abierto. "
        "Si alguna imagen queda pendiente, el documento indica cuál.",
        "#F8FAFC", "#CBD5E1", box_style,
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✓ Manual Docente PDF generado: {output_path}")


if __name__ == "__main__":
    public_pdf = os.path.join(ROOT_DIR, "web", "public", "MANUAL_DOCENTE_OPTICOMPROMISE.pdf")
    os.makedirs(os.path.dirname(public_pdf), exist_ok=True)
    build_teacher_pdf(public_pdf)
