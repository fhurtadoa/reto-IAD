"""
Generador del Manual de Usuario, Fundamentación Teórica, Casos de Uso y Glosario
para OptiCompromise (Opción 4 - IAD UNAL).
Usa fuentes TrueType DejaVu con cobertura Unicode matemática completa y genera
figuras directamente desde el motor real de optimización (api/core/).
"""
import json
import os
import shutil
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT_DIR, "api")
EXAMPLES_DIR = os.path.join(ROOT_DIR, "examples")
FIG_DIR = os.path.join(ROOT_DIR, "docs", "figuras")
os.makedirs(FIG_DIR, exist_ok=True)

if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from core.schemas import ModelDefinition
from core.payoff import compute_payoff_matrix
from core.compromise import solve_all_metrics
from core.pareto import compute_pareto_frontier


# =============================================================================
# 1. REGISTRO DE FUENTES UNICODE (DejaVu Sans / Mono de Matplotlib)
# =============================================================================
TTF_DIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(TTF_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(TTF_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Italic", os.path.join(TTF_DIR, "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-BoldItalic", os.path.join(TTF_DIR, "DejaVuSans-BoldOblique.ttf"))
                      if os.path.exists(os.path.join(TTF_DIR, "DejaVuSans-BoldOblique.ttf"))
                      else TTFont("DejaVu-BoldItalic", os.path.join(TTF_DIR, "DejaVuSans-Bold.ttf")))
registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Italic", boldItalic="DejaVu-BoldItalic")

pdfmetrics.registerFont(TTFont("DejaVuMono", os.path.join(TTF_DIR, "DejaVuSansMono.ttf")))
pdfmetrics.registerFont(TTFont("DejaVuMono-Bold", os.path.join(TTF_DIR, "DejaVuSansMono-Bold.ttf")))
registerFontFamily("DejaVuMono", normal="DejaVuMono", bold="DejaVuMono-Bold", italic="DejaVuMono", boldItalic="DejaVuMono-Bold")


# =============================================================================
# 2. GENERACIÓN DE FIGURAS DE ALTA RESOLUCIÓN DESDE EL MOTOR REAL
# =============================================================================
def _load_solve(filename: str):
    with open(os.path.join(EXAMPLES_DIR, filename), "r", encoding="utf-8") as f:
        model = ModelDefinition(**json.load(f))
    payoff = compute_payoff_matrix(model)
    solutions, weights = solve_all_metrics(model, payoff, weights=model.weights)
    pareto = compute_pareto_frontier(model, payoff, num_samples=21)
    return model, payoff, solutions, weights, pareto


def generate_figures():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.edgecolor": "#CBD5E1",
        "axes.linewidth": 0.9,
        "grid.color": "#E2E8F0",
        "grid.linestyle": "--",
        "grid.alpha": 0.8,
    })

    # --- FIGURA 1: Esquema de OptiCompromise (TopBar + Navegación + Panel 35% + Canvas 65% + Pie) ---
    fig, ax = plt.subplots(figsize=(10.5, 4.9), dpi=180)
    ax.set_xlim(0, 100); ax.set_ylim(0, 56); ax.axis("off")

    # Marco exterior
    ax.add_patch(patches.FancyBboxPatch((0.5, 0.5), 99, 55, boxstyle="round,pad=0.3", facecolor="#F3F4F8", edgecolor="#CBD5E1", lw=1.2))
    # Cabecera superior limpia (TopBar)
    ax.add_patch(patches.Rectangle((1.2, 49.4), 97.6, 5.2, facecolor="#FFFFFF", edgecolor="#CBD5E1", lw=1))
    ax.add_patch(patches.Rectangle((2.0, 50.6), 2.8, 2.8, facecolor="#E11D48", edgecolor="none"))
    ax.text(5.5, 52.0, "OptiCompromise — Programación de Compromiso Multiobjetivo · UNAL", fontsize=8.4, fontweight="bold", color="#0F172A", va="center")
    ax.text(85.0, 52.0, "[Tema claro/oscuro]", fontsize=6.7, color="#334155", va="center")

    # Barra de navegación de espacio de trabajo
    ax.add_patch(patches.Rectangle((1.2, 45.2), 97.6, 3.4, facecolor="#F8FAFC", edgecolor="#CBD5E1", lw=0.8))
    ax.text(2.5, 46.9, "Pestañas:  [Formular]  |  [Ver método]  |  [Explorar resultados]", fontsize=7.1, fontweight="bold", color="#0F172A", va="center")
    ax.text(65.0, 46.9, "Estado: ● Óptimo / Borrador sin aplicar", fontsize=6.9, color="#059669", fontweight="bold", va="center")

    # Panel Izquierdo (35%)
    ax.add_patch(patches.Rectangle((1.2, 5.2), 34.0, 39.2, facecolor="#FFFFFF", edgecolor="#CBD5E1", lw=1))
    ax.add_patch(patches.Rectangle((2.2, 40.7), 32.0, 2.9, facecolor="#F8FAFC", edgecolor="#CBD5E1", lw=0.8))
    ax.text(3.0, 42.15, "[Plantilla .xlsx] [Cargar] [Nuevo] [Guardar (.json)]", fontsize=5.8, fontweight="bold", color="#334155", va="center")

    ax.add_patch(patches.Rectangle((2.2, 37.3), 15.5, 2.6, facecolor="#E11D48"))
    ax.text(9.95, 38.6, "Modo Tabla", fontsize=6.7, color="#FFFFFF", fontweight="bold", ha="center", va="center")
    ax.add_patch(patches.Rectangle((18.2, 37.3), 16.0, 2.6, facecolor="#F1F5F9", edgecolor="#CBD5E1", lw=0.8))
    ax.text(26.2, 38.6, "Modo Algebraico (Borrador)", fontsize=6.2, color="#334155", fontweight="bold", ha="center", va="center")

    blocks_left = [
        (31.2, 5.3, "1. Variables (Nombre, Tipo ℝ/ℤ/{0,1}, Mín, Máx)"),
        (25.3, 5.2, "2. Objetivos (Max/Min + Coeficientes)"),
        (19.5, 5.1, "3. Restricciones (≤, ≥, = + Lado Derecho)"),
        (13.8, 5.0, "4. Vista Previa Matemática (LaTeX / KaTeX)"),
        (6.0, 7.1, "5. Preferencias & Pesos (Σw = 1.00)\n    Fijar peso · Edición numérica · Igualar pesos"),
    ]
    for y, h, lbl in blocks_left:
        ax.add_patch(patches.Rectangle((2.2, y), 32.0, h, facecolor="#F8FAFC", edgecolor="#E2E8F0", lw=0.8))
        ax.text(3.0, y + h / 2, lbl, fontsize=6.1, color="#1E293B", va="center")

    # Canvas Derecho (65%)
    ax.add_patch(patches.Rectangle((36.2, 5.2), 62.6, 39.2, facecolor="#FFFFFF", edgecolor="#CBD5E1", lw=1))
    ax.add_patch(patches.Rectangle((37.2, 40.7), 60.6, 2.9, facecolor="#F8FAFC", edgecolor="#E2E8F0", lw=0.8))
    ax.text(38.0, 42.15, "[Objetivos 2D] [Sensibilidad 21 pts] [Espacio 3D] [Radar] [Región Factible]", fontsize=6.1, fontweight="bold", color="#0F172A", va="center")
    ax.text(78.2, 42.15, "[Copiar] [Excel] [PDF]", fontsize=5.8, fontweight="bold", color="#E11D48", va="center")

    ax.add_patch(patches.Rectangle((37.2, 23.6), 60.6, 16.3, facecolor="#F8FAFC", edgecolor="#CBD5E1", lw=0.9))
    ax.text(67.5, 31.75, "Lienzo Interactivo Plotly (Pareto + Isodistancia + Zona Factible + Sensibilidad 3 paneles)\nIdeal ★ / Nadir ✕ / L₁ / L₂ / L∞ + Explorador de Puntos Pareto (Pesos × Métricas) + Descarga PNG", fontsize=6.8, color="#334155", ha="center", va="center")

    blocks_right = [
        (18.8, 4.1, "Comparativa de soluciones (Zᵢ, % Logro, Distancia Dₚ)"),
        (14.1, 4.0, "Decisiones Óptimas por Variable (Vector x* en L₁, L₂, L∞)"),
        (9.5, 4.0, "Ver método: Matriz de Pagos (q×q), Ideal (Z*), Nadir y Normalización por rango"),
        (6.0, 2.9, "Modo Rayos X (L∞ · λ*) · Tabla de logros y exportaciones"),
    ]
    for y, h, lbl in blocks_right:
        ax.add_patch(patches.Rectangle((37.2, y), 60.6, h, facecolor="#F8FAFC", edgecolor="#E2E8F0", lw=0.8))
        ax.text(38.2, y + h / 2, lbl, fontsize=6.5, color="#1E293B", va="center")

    # Pie de página (Footer)
    ax.add_patch(patches.Rectangle((1.2, 1.3), 97.6, 3.1, facecolor="#FFFFFF", edgecolor="#CBD5E1", lw=0.9))
    ax.text(2.4, 2.85, "Pie de página:  [Manual de usuario]  ·  [Guía docente]  ·  [Ejemplos (6 casos IAD)]", fontsize=6.4, fontweight="bold", color="#475569", va="center")
    ax.text(63.2, 2.85, "Fabián Andrés Hurtado Arango · Oscar David Arango Garcia · IAD UNAL", fontsize=5.9, color="#64748B", va="center")

    plt.tight_layout(pad=0.2)
    fig.savefig(os.path.join(FIG_DIR, "arquitectura.png"), dpi=180)
    plt.close(fig)

    # --- FIGURA 2: Caso Clase 15 (Espacio de Objetivos + Espacio de Decisiones) ---
    m_cel, p_cel, s_cel, _, par_cel = _load_solve("01_celdas_fotovoltaicas.json")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.2), dpi=180)

    # Subplot 1: Espacio de Objetivos
    px = [p.objectives[0] / 1000.0 for p in par_cel]
    py = [p.objectives[1] for p in par_cel]
    ax1.plot(px, py, color="#E11D48", lw=2.5, label="Unión de muestras Pareto", marker=".", zorder=3)
    ax1.scatter([p_cel.ideal_point[0] / 1000.0], [p_cel.ideal_point[1]], color="#D97706", s=190, marker="*", label="★ Ideal (800k, 200)", zorder=6)
    ax1.scatter([p_cel.anti_ideal_point[0] / 1000.0], [p_cel.anti_ideal_point[1]], color="#BE123C", s=95, marker="X", label="✕ Nadir aprox. (300k, 600)", zorder=6)
    for k, lbl, col, mk, dx, dy in [
        ("L1", "L₁ (600k, 400)", "#2563EB", "s", -75, 16),
        ("L2", "L₂ (595.1k, 396.7)", "#334155", "o", -110, -28),
        ("L_inf", "L∞ (572.7k, 381.8)", "#E11D48", "D", -120, 12),
    ]:
        sol = s_cel[k]
        ax1.scatter([sol.objectives[0] / 1000.0], [sol.objectives[1]], color=col, s=85, marker=mk, edgecolors="#FFFFFF", lw=1, label=lbl, zorder=7)
    ax1.set_title("Clase 15: Espacio de Objetivos (Z₁ vs Z₂)", fontsize=10, fontweight="bold")
    ax1.set_xlabel("Utilidad Total (miles USD)", fontsize=8.5)
    ax1.set_ylabel("Emisión Contaminantes (kg)", fontsize=8.5)
    ax1.grid(True); ax1.legend(fontsize=7.2, loc="upper left")

    # Subplot 2: Espacio de Decisiones (Polígono Factible)
    poly_x = [0, 0, 200, 300, 300, 0]
    poly_y = [100, 200, 200, 100, 0, 100]
    ax2.fill(poly_x, poly_y, facecolor="#0F766E", alpha=0.14, edgecolor="#0F766E", lw=1.8, label="Región Factible")
    for k, lbl, col, mk, ox, oy in [
        ("L1", "L₁ (0, 200)", "#2563EB", "s", 14, -6),
        ("L2", "L₂ (0, 198.4)", "#334155", "o", 14, -20),
        ("L_inf", "L∞ (0, 190.9)", "#E11D48", "D", 14, -34),
    ]:
        sol = s_cel[k]
        vx, vy = sol.variables[m_cel.variables[0].name], sol.variables[m_cel.variables[1].name]
        ax2.scatter([vx], [vy], color=col, s=85, marker=mk, edgecolors="#FFFFFF", lw=1, label=lbl, zorder=7)
        ax2.annotate(lbl, (vx, vy), xytext=(vx + ox, vy + oy), fontsize=7.5, color=col, fontweight="bold")
    ax2.set_title("Clase 15: Espacio de Decisiones (x₁ vs x₂)", fontsize=10, fontweight="bold")
    ax2.set_xlabel("x₁ (Celdas Fotovoltaicas)", fontsize=8.5)
    ax2.set_ylabel("x₂ (Celdas GP)", fontsize=8.5)
    ax2.set_xlim(-15, 320); ax2.set_ylim(-10, 225)
    ax2.grid(True); ax2.legend(fontsize=7.2, loc="lower right")

    plt.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "clase15_pareto_iso.png"), dpi=180)
    plt.close(fig)

    # --- FIGURA 3: Triobjetivo 3D (Espacio 3D + Radar) ---
    m_tri, p_tri, s_tri, _, par_tri = _load_solve("04_triobjetivo_3d.json")
    fig = plt.figure(figsize=(10.5, 4.4), dpi=180)
    ax3d = fig.add_subplot(121, projection="3d")
    ax3d.scatter(
        [p.objectives[0] for p in par_tri],
        [p.objectives[1] for p in par_tri],
        [p.objectives[2] for p in par_tri],
        c="#0F766E", s=16, alpha=0.45, label="Muestra Pareto 3D"
    )
    ax3d.scatter([p_tri.ideal_point[0]], [p_tri.ideal_point[1]], [p_tri.ideal_point[2]], c="#D97706", s=150, marker="*", label="★ Ideal (260, 0, 300)")
    ax3d.scatter([p_tri.anti_ideal_point[0]], [p_tri.anti_ideal_point[1]], [p_tri.anti_ideal_point[2]], c="#BE123C", s=80, marker="X", label="✕ Nadir aprox. (0, 280, 0)")
    for k, lbl, col, mk in [("L1", "L₁", "#2563EB", "s"), ("L2", "L₂", "#334155", "o"), ("L_inf", "L∞", "#E11D48", "D")]:
        sol = s_tri[k]
        ax3d.scatter([sol.objectives[0]], [sol.objectives[1]], [sol.objectives[2]], c=col, s=80, marker=mk, label=lbl)
    ax3d.set_title("Sostenibilidad Triobjetivo 3D", fontsize=9.5, fontweight="bold")
    ax3d.set_xlabel("Retorno (kUSD)", fontsize=7.5)
    ax3d.set_ylabel("CO₂ eq", fontsize=7.5)
    ax3d.set_zlabel("Social (pts)", fontsize=7.5)
    ax3d.legend(fontsize=6.5, loc="upper left")

    # Radar de % Logro de Flota 4 Objetivos
    m_flo, _, s_flo, _, _ = _load_solve("05_flota_vehiculos.json")
    ax_rad = fig.add_subplot(122, polar=True)
    cats = ["Costo", "Autonomía", "T. Carga", "Seguridad"]
    N = len(cats)
    angles = [n / float(N) * 2 * np.pi for n in range(N)] + [0.0]
    ax_rad.set_xticks(angles[:-1]); ax_rad.set_xticklabels(cats, fontsize=8, fontweight="bold")
    ax_rad.set_ylim(min(0, *(v for sol in s_flo.values() for v in sol.achievement_pct)), 108)
    ax_rad.plot(angles, [100] * (N + 1), lw=1.4, ls="--", color="#D97706", label="Ideal (100%)")
    for k, lbl, col in [("L1", "L₁", "#2563EB"), ("L2", "L₂", "#334155"), ("L_inf", "L∞", "#E11D48")]:
        vals = s_flo[k].achievement_pct.copy()
        vals += [vals[0]]
        ax_rad.plot(angles, vals, lw=2, color=col, label=lbl)
        ax_rad.fill(angles, vals, color=col, alpha=0.10)
    ax_rad.set_title("Flota 4 Objetivos: Radar % Logro", fontsize=9.5, fontweight="bold", y=1.10)
    ax_rad.legend(fontsize=7, loc="upper right", bbox_to_anchor=(1.25, 1.12))

    plt.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "triobjetivo_3d_y_radar.png"), dpi=180)
    plt.close(fig)

    # --- FIGURA 4: MIP Discreto (Sin línea falsa continua) ---
    _, p_mip, s_mip, _, par_mip = _load_solve("03_mip_produccion.json")
    fig, ax = plt.subplots(figsize=(9.5, 3.8), dpi=180)
    for grp, col, mk, lbl in [("L1", "#2563EB", "^", "Pareto L₁ (MIP)"), ("L2", "#64748B", "o", "Pareto L₂ (B&B)"), ("L_inf", "#E11D48", "D", "Pareto L∞ (MIP)")]:
        pts = [p for p in par_mip if p.metric == grp]
        if pts:
            ax.scatter([p.objectives[0] for p in pts], [p.objectives[1] for p in pts], color=col, marker=mk, s=55, alpha=0.8, label=lbl, zorder=4)
    ax.scatter([p_mip.ideal_point[0]], [p_mip.ideal_point[1]], color="#D97706", s=190, marker="*", label="★ Ideal (1350, 230)", zorder=6)
    ax.scatter([p_mip.anti_ideal_point[0]], [p_mip.anti_ideal_point[1]], color="#BE123C", s=95, marker="X", label="✕ Nadir aprox. (750, 380)", zorder=6)
    ax.scatter([s_mip["L1"].objectives[0]], [s_mip["L1"].objectives[1]], color="#2563EB", s=110, marker="s", edgecolors="#FFFFFF", lw=1.2, label="Solución L₁", zorder=7)
    for metric, label, color, marker in [
        ("L2", "Solución L₂", "#334155", "o"),
        ("L_inf", "Solución L∞", "#E11D48", "D"),
    ]:
        ax.scatter(*s_mip[metric].objectives, color=color, s=110, marker=marker,
                   edgecolors="#FFFFFF", lw=1.2, label=label, zorder=7)

    ax.set_title("Producción mixta: aproximación de Pareto mediante puntos", fontsize=9.5, fontweight="bold", y=1.22)
    ax.set_xlabel("Rendimiento (USD)", fontsize=8.5)
    ax.set_ylabel("Costo Operativo (USD)", fontsize=8.5)
    ax.grid(True); ax.legend(fontsize=7.0, loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=3, frameon=True)
    plt.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "mip_discreto.png"), dpi=180)
    plt.close(fig)


# =============================================================================
# 3. DECORACIÓN DE PÁGINAS DEL PDF
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
        self.drawString(48, 754, "OptiCompromise — Manual de Usuario y Casos de Uso | IAD UNAL")
        self.drawRightString(612 - 48, 754, "Opción 4: Programación de Compromiso")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(48, 748, 612 - 48, 748)
        self.line(48, 44, 612 - 48, 44)
        self.drawString(48, 33, "Facultad de Minas — Universidad Nacional de Colombia (Sede Medellín)")
        self.drawRightString(612 - 48, 33, f"Página {self._pageNumber} de {page_count}")
        self.restoreState()


def _scaled_image(path: str, max_width: float, max_height: float | None = None) -> Image:
    with PILImage.open(path) as im:
        w, h = im.size
    scale = max_width / float(w)
    if max_height is not None and h * scale > max_height:
        scale = max_height / float(h)
    return Image(path, width=w * scale, height=h * scale)


def build_pdf(output_path: str):
    generate_figures()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=48,
        rightMargin=48,
        topMargin=54,
        bottomMargin=52,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("TitleV2", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=23, leading=28, textColor=colors.HexColor("#0F172A"), spaceAfter=4)
    subtitle_style = ParagraphStyle("SubV2", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=11, leading=15, textColor=colors.HexColor("#E11D48"), spaceAfter=12)
    h1_style = ParagraphStyle("H1V2", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=13.5, leading=18, textColor=colors.HexColor("#0F172A"), spaceBefore=10, spaceAfter=4, keepWithNext=True)
    h2_style = ParagraphStyle("H2V2", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=10.5, leading=14, textColor=colors.HexColor("#E11D48"), spaceBefore=8, spaceAfter=3, keepWithNext=True)
    body_style = ParagraphStyle("BodyV2", parent=styles["Normal"], fontName="DejaVu", fontSize=8.8, leading=13, textColor=colors.HexColor("#1E293B"), spaceAfter=5)
    bullet_style = ParagraphStyle("BulletV2", parent=styles["Normal"], fontName="DejaVu", fontSize=8.5, leading=12.5, textColor=colors.HexColor("#1E293B"), leftIndent=12, spaceAfter=3)
    th_style = ParagraphStyle("THV2", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=7.8, leading=10, textColor=colors.white, alignment=1)
    td_style = ParagraphStyle("TDV2", parent=styles["Normal"], fontName="DejaVu", fontSize=7.8, leading=10.5, textColor=colors.HexColor("#0F172A"))
    td_bold = ParagraphStyle("TDBV2", parent=styles["Normal"], fontName="DejaVu-Bold", fontSize=7.8, leading=10.5, textColor=colors.HexColor("#0F172A"))
    code_style = ParagraphStyle("CodeV2", parent=styles["Normal"], fontName="DejaVuMono", fontSize=7.5, leading=10.5, textColor=colors.HexColor("#0F172A"))
    cap_style = ParagraphStyle("CapV2", parent=styles["Normal"], fontName="DejaVu-Italic", fontSize=7.8, leading=10, textColor=colors.HexColor("#475569"), alignment=1, spaceBefore=3, spaceAfter=8)
    box_style = ParagraphStyle("BoxV2", parent=styles["Normal"], fontName="DejaVu", fontSize=8.3, leading=12.2, textColor=colors.HexColor("#0F172A"))

    story = []

    # =========================================================================
    # PORTADA
    # =========================================================================
    story.append(Spacer(1, 14))
    story.append(Paragraph("UNIVERSIDAD NACIONAL DE COLOMBIA — FACULTAD DE MINAS", ParagraphStyle("UH", fontName="DejaVu-Bold", fontSize=9.5, leading=12, textColor=colors.HexColor("#E11D48"))))
    story.append(Paragraph("INTRODUCCIÓN AL ANÁLISIS DE DECISIONES (IAD) | CONCURSO DE HERRAMIENTAS — OPCIÓN 4", ParagraphStyle("DH", fontName="DejaVu", fontSize=8, leading=11, textColor=colors.HexColor("#64748B"), spaceAfter=12)))
    story.append(HRFlowable(width="100%", thickness=2.2, color=colors.HexColor("#E11D48"), spaceAfter=14))

    story.append(Paragraph("OptiCompromise", title_style))
    story.append(Paragraph("Manual de Usuario, Fundamentación Matemática, Casos de Validación y Glosario", subtitle_style))
    story.append(Paragraph(
        "Herramienta web interactiva de software libre para formular, normalizar, resolver y visualizar problemas de decisión multiobjetivo lineales (continuos y enteros mixtos MIP) mediante <b>Programación de Compromiso (L₁, L₂ y L∞)</b>.",
        body_style
    ))
    story.append(Spacer(1, 6))

    meta_rows = [
        [Paragraph("<b>Asignatura y Reto</b>", td_bold), Paragraph("Introducción al Análisis de Decisiones (2026-2S) · Opción 4: Programación de Compromiso", td_style)],
        [Paragraph("<b>Docente / Apoyo</b>", td_bold), Paragraph("Patricia Jaramillo Álvarez, PhD  |  Jaime Andrés Díaz Guerra, MSc", td_style)],
        [Paragraph("<b>Autores</b>", td_bold), Paragraph("Fabián Andrés Hurtado Arango · Oscar David Arango Garcia", td_style)],
        [Paragraph("<b>Tecnología Libre</b>", td_bold), Paragraph("Next.js 15 (15.5.29) + React + Tailwind + Plotly.js + KaTeX  |  FastAPI + SciPy (HiGHS & SLSQP) + openpyxl + SheetJS CE 0.20.3", td_style)],
        [Paragraph("<b>Licencia</b>", td_bold), Paragraph("MIT License (uso, modificación y distribución académica abierta)", td_style)],
    ]
    t_meta = Table(meta_rows, colWidths=[125, 391])
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

    story.append(_scaled_image(os.path.join(FIG_DIR, "arquitectura.png"), max_width=516, max_height=232))
    story.append(Paragraph("Figura 1: Arquitectura visual de OptiCompromise (cabecera, secciones de trabajo, preferencias y visualizaciones).", cap_style))
    story.append(Spacer(1, 8))
    story.append(Table(
        [[Paragraph(
            "<b>Declaración de Software Libre e IA (Sección 12):</b> Todo el proyecto está licenciado bajo MIT y emplea exclusivamente bibliotecas libres (SciPy BSD-3, NumPy BSD-3, FastAPI MIT, Next.js 15/React MIT, Plotly MIT, KaTeX MIT, openpyxl MIT, SheetJS CE 0.20.3 Apache-2.0, ReportLab BSD). Se utilizó IA como apoyo en arquitectura, pruebas y contraste de las fórmulas con el material de IAD.",
            box_style
        )]],
        colWidths=[516],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF1F2")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E11D48")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    ))
    story.append(PageBreak())

    # =========================================================================
    # SECCIÓN 1: FUNDAMENTACIÓN TEÓRICA Y MATEMÁTICA
    # =========================================================================
    story.append(Paragraph("1. Fundamentación Teórica y Formulación Matemática", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E11D48"), spaceAfter=8))
    story.append(Paragraph(
        "En problemas reales con <i>q ≥ 2</i> criterios en conflicto (por ejemplo maximizar utilidad económica mientras se minimiza contaminación), los óptimos individuales pueden ser incompatibles. La <b>programación de compromiso</b> minimiza una distancia ponderada al <b>punto ideal (Z*)</b> sobre la región factible.",
        body_style
    ))

    story.append(Paragraph("1.1 Matriz de pagos, punto ideal y nadir aproximado", h2_style))
    story.append(Paragraph(
        "El motor resuelve primero cada objetivo <i>Z_k(x)</i> en solitario sobre la región factible <i>X</i> (entre óptimos alternativos, mejora la suma de los otros objetivos escalados) y construye la matriz <i>M[k, i] = Z_i(x*(k))</i>:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Punto Ideal (Z*):</b> Z*_i = max_k M[k, i] si Z_i se maximiza, o min_k M[k, i] si Z_i se minimiza (diagonal de la matriz).<br/>"
        "• <b>Nadir aproximado (Z_peor):</b> peor valor observado por columna de pagos. El nadir teórico toma los peores valores entre las soluciones eficientes. El antiideal los toma sobre toda la región factible.<br/>"
        "• <b>Rango de Conflicto:</b> R_i = |Z*_i − Z_peor,i|. Si el rango de pagos es cero, se usa el rango factible si es positivo y finito. Un objetivo constante tiene brecha cero. Si el peor extremo factible no se puede calcular, se usa una unidad del objetivo.",
        bullet_style
    ))

    story.append(Paragraph("1.2 Normalización por rango y métricas L₁, L₂ y L∞", h2_style))
    story.append(Paragraph(
        "La desviación D_i(x) divide la brecha al ideal por el rango R_i. Para maximizar se resta Z_i(x) del ideal y para minimizar se resta el ideal de Z_i(x). El logro es <b>100 · (1 − D_i(x)) %</b>. Una brecha superior a 1 da un logro negativo.",
        body_style
    ))
    met_rows = [
        [Paragraph("<b>Métrica</b>", th_style), Paragraph("<b>Formulación Exacta Resuelta</b>", th_style), Paragraph("<b>Comportamiento Decisional</b>", th_style)],
        [
            Paragraph("<b>L₁ (Manhattan)</b>", td_bold),
            Paragraph("min ∑ w_i · D_i(x)<br/>Solver: LP / MILP (HiGHS)", code_style),
            Paragraph("<b>Compensatorio / Utilitarista:</b> permite sacrificar un objetivo si otro mejora más; tiende a vértices extremos.", td_style),
        ],
        [
            Paragraph("<b>L₂ (Euclidiana)</b>", td_bold),
            Paragraph("min ∑ (w_i · D_i(x))²<br/>D₂ = √(∑ (w_i · D_i)²)<br/>Solver: QP SLSQP / Branch-and-Bound MIP", code_style),
            Paragraph("Eleva al cuadrado cada brecha ya ponderada. La función cuadrática es convexa y puede tener varios óptimos.", td_style),
        ],
        [
            Paragraph("<b>L∞ (Minimax)</b>", td_bold),
            Paragraph("min λ  s.a.  w_i · D_i(x) ≤ λ (∀i), λ ≥ 0<br/>Solver: LP / MILP Minimax (HiGHS)", code_style),
            Paragraph("Reduce la mayor brecha ponderada. Las restricciones activas comparten esa brecha.", td_style),
        ],
    ]
    t_met = Table(met_rows, colWidths=[85, 210, 221])
    t_met.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111524")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t_met)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Convención de IAD:</b> Clase 15 (pp. 9 y 19) eleva al cuadrado la brecha ya ponderada. Minimizar su suma equivale a minimizar la raíz. En los empates de L∞ y de L₁ con pesos nulos, el motor busca reducir la suma de brechas manteniendo el valor óptimo primario.",
        body_style
    ))

    story.append(PageBreak())
    # =========================================================================
    # SECCIÓN 2: GUÍA PASO A PASO DE OPTICOMPROMISE
    # =========================================================================
    story.append(Paragraph("2. Guía Paso a Paso de Uso (Sin Escribir Código)", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E11D48"), spaceAfter=8))

    steps_rows = [
        [Paragraph("<b>Paso</b>", th_style), Paragraph("<b>Zona de la Interfaz</b>", th_style), Paragraph("<b>Acción del Usuario</b>", th_style)],
        [Paragraph("<b>1. Cargar o Crear</b>", td_bold), Paragraph("<b>Formular</b> y Pie de página", td_style), Paragraph("Abre cualquiera de los 6 casos precargados desde el botón <b>Ejemplos</b> del pie de página o mediante <b>Cargar ejercicio</b> (<font face='DejaVuMono'>.xlsx</font> de <font face='DejaVuMono'>ejercicios/</font>, <font face='DejaVuMono'>.csv</font> con coma o punto y coma, o <font face='DejaVuMono'>.json</font>). Pulsa <b>Nuevo modelo</b> para empezar desde cero, <b>Guardar (.json)</b> para descargar la formulación actual, o <b>Obtener plantilla (.xlsx)</b> para diligenciar la hoja <b>Modelo</b>.", td_style)],
        [Paragraph("<b>2. Formular Modelo</b>", td_bold), Paragraph("Pestaña <b>Formular</b> (<b>Modo Tabla</b> / <b>Modo Algebraico</b>)", td_style), Paragraph("Define variables (ℝ, ℤ, {0,1} y cotas), objetivos (Max/Min) y restricciones (≤, ≥, =). En <b>Modo Algebraico</b> escribe ecuaciones como <font face='DejaVuMono'>Max Z1 = 50*x1 + 120*x2</font>; mientras existan cambios sin aplicar, el estado marca <b>Borrador sin aplicar</b> y bloquea vistas/exportación hasta pulsar <b>Aplicar Ecuaciones y Resolver</b>. La <b>Vista Previa LaTeX</b> se actualiza en vivo.", td_style)],
        [Paragraph("<b>3. Ajustar Pesos</b>", td_bold), Paragraph("Panel <b>Preferencias</b>", td_style), Paragraph("Escribe un peso o ajusta su deslizador. Pulsa <b>Fijar peso</b> para mantenerlo al ajustar los demás. Los pesos libres se redistribuyen y conservan la suma de 1. Para <b>Igualar pesos</b>, desbloquea los pines que tengan un valor distinto al reparto equitativo.", td_style)],
        [Paragraph("<b>4. Ver Método y Explorar</b>", td_bold), Paragraph("Pestañas <b>Ver método</b> y <b>Explorar resultados</b>", td_style), Paragraph("En <b>Explorar resultados</b> analiza <b>Objetivos 2D</b> (Pareto + Isodistancia + Zona Factible), <b>Sensibilidad de pesos</b> (21 puntos entre 0 y 1, en tres paneles), <b>Espacio 3D</b>, <b>Radar (% Logro)</b> y <b>Región Factible</b> (2 variables, con malla discreta ℤ). En <b>Ver método</b> inspecciona la Matriz de Pagos, normalización y el acordeón <b>Modo Rayos X (L∞)</b>.", td_style)],
        [Paragraph("<b>5. Exportar</b>", td_bold), Paragraph("<b>Explorar resultados</b>", td_style), Paragraph("Descarga <b>Excel (.xlsx)</b> o <b>PDF (.pdf)</b> con el modelo, resultados e imágenes de todas las gráficas aplicables. La hoja <b>Modelo</b> del Excel se puede reabrir desde <b>Formular</b>.", td_style)],
    ]
    t_steps = Table(steps_rows, colWidths=[85, 130, 301])
    t_steps.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111524")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_steps)
    story.append(Spacer(1, 8))

    # Capturas reales recientes (proporcionales con PIL.Image)
    cap_desktop = os.path.join(ROOT_DIR, "docs", "capturas", "opticompromise-escritorio.jpg")
    cap_method = os.path.join(ROOT_DIR, "docs", "capturas", "opticompromise-metodo.jpg")
    if os.path.exists(cap_desktop) and os.path.exists(cap_method):
        t_caps_light = Table(
            [[
                _scaled_image(cap_desktop, max_width=252, max_height=182),
                _scaled_image(cap_method, max_width=252, max_height=182),
            ]],
            colWidths=[258, 258],
            style=TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]),
        )
        story.append(t_caps_light)
        story.append(Paragraph("Figura 2: Capturas reales de OptiCompromise — Explorar resultados con Objetivos 2D y Preferencias (izq.) y vista Ver método con Matriz de pagos del mismo ejercicio (der.).", cap_style))
    story.append(PageBreak())

    # =========================================================================
    # SECCIÓN 3: CASOS DE USO Y VALIDACIÓN CRUZADA
    # =========================================================================
    story.append(Paragraph("3. Casos de Demostración y Validación Oficial", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E11D48"), spaceAfter=6))

    story.append(Paragraph("3.1 Caso Base 1: Planificación de Celdas Fotovoltaicas (Clase 15)", h2_style))
    story.append(Paragraph(
        "Problema biobjetivo clásico del curso: maximizar Utilidad (1000x₁ + 3000x₂) y minimizar Contaminantes (x₁ + 2x₂) sujeto a x₁ + x₂ ≤ 400, 1000x₁ + 3000x₂ ≥ 300.000, x₁ ∈ [0, 300], x₂ ∈ [0, 200]. Con pesos iguales (0.5, 0.5), L₁ elige el vértice compensatorio (0, 200) con logros 60.0% / 50.0%, L₂ suaviza en (0, 198.36) con 59.02% / 50.82% y L∞ iguala ambos logros en <b>54.55%</b> en (0, 190.91).",
        body_style
    ))
    story.append(_scaled_image(os.path.join(FIG_DIR, "clase15_pareto_iso.png"), max_width=500, max_height=205))
    story.append(Paragraph("Figura 3: Espacio de objetivos con muestras de Pareto (izquierda) y región factible en espacio de decisiones (derecha) para Clase 15.", cap_style))

    story.append(Paragraph("3.2 Casos Avanzados y Bonus: Triobjetivo 3D, Flota (4Z) y Producción Mixta MIP", h2_style))
    story.append(Paragraph(
        "La herramienta incorpora casos avanzados verificados: (a) <b>Sostenibilidad Triobjetivo 3D</b> (3 variables continuas, 3 objetivos Max/Min/Max en 3D interactivo) y <b>Flota de Vehículos Eléctricos</b> (6 variables, 4 criterios, perfil Radar); y (b) <b>Producción Mixta MIP</b> con variable continua x₁, entera x₂ ∈ ℤ y binaria y₁ ∈ {0, 1}, cuya muestra discreta se dibuja con puntos individuales.",
        body_style
    ))
    story.append(_scaled_image(os.path.join(FIG_DIR, "triobjetivo_3d_y_radar.png"), max_width=500, max_height=210))
    story.append(Paragraph("Figura 4: Visualización 3D del caso Triobjetivo (izquierda) y gráfico Radar de % de logro para Flota de 4 objetivos (derecha).", cap_style))

    story.append(PageBreak())
    story.append(_scaled_image(os.path.join(FIG_DIR, "mip_discreto.png"), max_width=495, max_height=198))
    story.append(Paragraph("Figura 5: Muestra de Pareto del caso Producción Mixta MIP. En L₂, la ramificación y poda puede devolver una solución factible sin certificado si se agota el presupuesto.", cap_style))

    cap_mobile = os.path.join(ROOT_DIR, "docs", "capturas", "opticompromise-movil.jpg")
    cap_3d = os.path.join(ROOT_DIR, "docs", "capturas", "opticompromise-3d.jpg")
    if os.path.exists(cap_mobile) and os.path.exists(cap_3d):
        t_caps_more = Table(
            [[
                _scaled_image(cap_mobile, max_width=252, max_height=182),
                _scaled_image(cap_3d, max_width=252, max_height=182),
            ]],
            colWidths=[258, 258],
            style=TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]),
        )
        story.append(Spacer(1, 6))
        story.append(t_caps_more)
        story.append(Paragraph("Figura 6: Exploración de objetivos en móvil (izq.) y Espacio 3D del modelo Sostenibilidad en tema oscuro (der.).", cap_style))

    story.append(PageBreak())
    story.append(Paragraph("4. Resultados de los casos de demostración", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E11D48"), spaceAfter=6))

    val_rows = [
        [Paragraph("<b>Caso Validado</b>", th_style), Paragraph("<b>Ideal / Nadir aprox.</b>", th_style), Paragraph("<b>Solución L₁</b>", th_style), Paragraph("<b>Solución L₂</b>", th_style), Paragraph("<b>Solución L∞</b>", th_style)],
    ]

    def values(data):
        return "(" + ", ".join(f"{value:,.2f}" for value in data) + ")"

    for filename, name in [
        ("01_celdas_fotovoltaicas.json", "Celdas · Clase 15"),
        ("02_problema_transporte.json", "Transporte · Taller 3"),
        ("06_produccion_papel.json", "Papel · Taller 3 (n = 6)"),
        ("04_triobjetivo_3d.json", "Sostenibilidad 3D"),
        ("03_mip_produccion.json", "Producción mixta"),
        ("05_flota_vehiculos.json", "Flota eléctrica"),
    ]:
        with open(os.path.join(EXAMPLES_DIR, filename), encoding="utf-8") as file:
            model = ModelDefinition.model_validate_json(file.read())
        if filename == "06_produccion_papel.json":
            model.constraints[3].rhs = 83
            model.weights = [0.56, 0.44]
        payoff = compute_payoff_matrix(model)
        solutions, weights = solve_all_metrics(model, payoff, model.weights)
        row = [
            Paragraph(f"<b>{name}</b><br/>w = {values(weights)}", td_style),
            Paragraph(f"{values(payoff.ideal_point)}<br/>{values(payoff.anti_ideal_point)}", td_style),
        ]
        for sol in solutions.values():
            state = "" if sol.status == "optimal" else "<br/>Sin certificado"
            row.append(Paragraph(f"Z = {values(sol.objectives)}<br/>D = {sol.aggregate_distance:.4f}{state}", td_style))
        val_rows.append(row)
    t_val = Table(val_rows, colWidths=[106, 98, 104, 104, 104])
    t_val.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111524")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_val)
    story.append(Spacer(1, 4))

    # =========================================================================
    # SECCIÓN 5: GLOSARIO DE CONCEPTOS (OBLIGATORIO E5)
    # =========================================================================
    story.append(Paragraph("5. Glosario de Conceptos", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E11D48"), spaceAfter=8))

    glossary = [
        ("Programación de Compromiso", "Metodología de decisión multicriterio que selecciona la solución factible más cercana al Punto Ideal según una métrica de distancia Lp y un vector de pesos w."),
        ("Matriz de Pagos (Payoff Matrix)", "Tabla cuadrada q×q cuya fila k contiene los valores de todos los objetivos evaluados en el óptimo individual x*(k) del k-ésimo objetivo."),
        ("Punto Ideal (Z*)", "Vector formado por el mejor desempeño individual de cada objetivo (diagonal de la matriz de pagos). Es inalcanzable simultáneamente cuando existe conflicto."),
        ("Nadir aproximado (Z_peor)", "Peor valor de cada columna de pagos. El nadir teórico considera las soluciones eficientes. El antiideal considera todas las soluciones factibles."),
        ("Normalización por Rango", "Cociente entre la brecha al ideal y el rango. Puede superar 1 cuando se usa la referencia de pagos."),
        ("Grado de Logro (Z'_i)", "Porcentaje de satisfacción respecto al ideal: Z'_i(x) = 100 · (1 − D_i(x))%. Vale 100 % en el ideal. Con rango de pagos positivo, vale 0 % en la referencia de pagos."),
        ("Métrica L₁ (Manhattan)", "Distancia ponderada lineal ∑ w_i D_i(x). Permite compensación total entre objetivos y suele ubicarse en vértices extremos."),
        ("Métrica L₂ (Euclidiana)", "Distancia euclidiana de brechas ponderadas √(∑ (w_i D_i(x))²)."),
        ("Métrica L∞ (Minimax / λ*)", "Minimiza la máxima desviación ponderada λ = max_i [w_i · D_i(x)]. Las restricciones activas comparten la máxima brecha ponderada."),
        ("Frontera Eficiente de Pareto", "Conjunto de soluciones factibles no dominadas en todo el modelo. La aplicación filtra dominancia entre las soluciones muestreadas."),
        ("Curvas de Isodistancia", "Contornos de igual distancia en los dos ejes elegidos. Su forma depende de la métrica y de los pesos."),
        ("Programación Entera Mixta (MIP)", "Extensión con variables continuas (ℝ), enteras (ℤ) y binarias ({0,1}), tratada con HiGHS para L₁ y L∞ y ramificación y poda con presupuesto para L₂."),
        ("Rango de pagos nulo", "Ideal y peor valor de la columna de pagos coinciden. El objetivo puede variar en la región factible."),
    ]
    gl_rows = [[Paragraph(f"<b>{term}</b>", td_bold), Paragraph(defn, td_style)] for term, defn in glossary]
    t_gl = Table(gl_rows, colWidths=[145, 371])
    t_gl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
    ]))
    story.append(t_gl)
    story.append(Spacer(1, 3))



    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✓ Manual PDF generado: {output_path}")


if __name__ == "__main__":
    public_pdf = os.path.join(ROOT_DIR, "web", "public", "MANUAL_DE_USUARIO_Y_CASOS_DE_USO_OPTICOMPROMISE.pdf")
    os.makedirs(os.path.dirname(public_pdf), exist_ok=True)
    build_pdf(public_pdf)
