"""
Pipe Stress Infinity — Simulador Visual (Streamlit)
"""

# ── Fix NumPy in-memory patch (no escribe archivos) ──────
import os, sys
# ─────────────────────────────────────────────────────────

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import subprocess, tempfile, re
import pandas as pd

# ── Constantes de color ───────────────────────────────────
BG         = "#0d1117"
PIPE_COL   = "#58a6ff"
DEFORM_W   = "#f0883e"
DEFORM_T   = "#ff7b72"
ANCHOR_COL = "#3fb950"
NODE_COL   = "#e6edf3"
SUBTEXT    = "#7d8590"
GRID_COL   = "#21262d"
PANEL2     = "#1c2128"
BORDER     = "#30363d"
GRAV_COL   = "#fbbf24"

PIPE_SIZES = ["2","3","4","6","8","10","12","16"]
SCHEDULES  = ["10","20","40","80","160"]

CONFIGS = [
    "Voladizo (1 apoyo empotrado)",
    "Simplemente apoyado (2 apoyos)",
    "Forma L (codo 90°)",
    "Forma U (lazo de expansión)",
    "Forma Z (offset)",
]

ORIENTATIONS = [
    "Horizontal  — caños en X, gravedad ↓ (-Y)",
    "Vertical    — caños en Y, gravedad ↓ (-Y)",
    "En planta   — caños en XY, gravedad ↓ (-Z, ⊗ fuera del plano)",
]

# ── PSI Header con patch en memoria ──────────────────────
PSI_HEADER = """
import inspect, psi.loads as _psi_loads
_src = inspect.getsource(_psi_loads)
_src_fixed = _src.replace('wxl, wyl, wzl = wl\\n', 'wxl, wyl, wzl = wl[:, 0]\\n')
exec(compile(_src_fixed, _psi_loads.__file__ or '<psi.loads>', 'exec'), _psi_loads.__dict__)
from psi.loads import Weight, Thermal

from psi.app import App; app = App()
from psi.model import Model
from psi.elements import Run
from psi.sections import Pipe
from psi.material import Material
from psi.loads import Weight, Thermal
from psi.loadcase import LoadCase
from psi.reports import Movements
from psi.codes.b311 import B31167
from psi.supports import Anchor
from psi.point import Point

mdl = Model('sim')
{vertical_line}
pipe1 = Pipe.from_file('pipe1', '{size}', '{sched}')
mat1 = Material.from_file('mat1', 'A53A', 'B31.1')
"""


# ══════════════════════════════════════════════════════════
# GEOMETRÍA PSI — devuelve (geom_script, nodes, elems, anchors)
# ══════════════════════════════════════════════════════════

def build_geometry(config, L1, L2, L3, orientation):
    """
    Genera el script de geometría PSI y las posiciones 2D de los nodos.

    Horizontal : runs en ±X, caídas en ±Y   → visualización XY
    Vertical   : runs en ±Y, ramas en ±X    → visualización XY (caño sube)
    En planta  : runs en ±X/±Y (idem Horiz) → visualización XY (top view)
                 gravity='z', peso deflecta en Z (fuera del plano)
    """
    is_vertical = "Vertical" in orientation

    if is_vertical:
        return _geom_vertical(config, L1, L2, L3)
    else:
        # Horizontal y En planta comparten la misma geometría XY
        return _geom_horizontal(config, L1, L2, L3)


def _geom_horizontal(config, L1, L2, L3):
    """Sistema en plano XY: runs horizontales en X, caídas en -Y."""
    if config == "Voladizo (1 apoyo empotrado)":
        g = f"pt10=Point(10)\nrun20=Run(20,{L1})\nanc1=Anchor('A1',10)\nanc1.apply([run20])"
        return g, {10:(0,0),20:(L1,0)}, ["run20"], [10]

    elif config == "Simplemente apoyado (2 apoyos)":
        g = (f"pt10=Point(10)\nrun20=Run(20,{L1})\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',20)\nanc2.apply([run20])")
        return g, {10:(0,0),20:(L1,0)}, ["run20"], [10,20]

    elif config == "Forma L (codo 90°)":
        g = (f"pt10=Point(10)\nrun20=Run(20,{L1})\nrun30=Run(30,0,-{L2})\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',30)\nanc2.apply([run30])")
        return g, {10:(0,0),20:(L1,0),30:(L1,-L2)}, ["run20","run30"], [10,30]

    elif config == "Forma U (lazo de expansión)":
        g = (f"pt10=Point(10)\nrun20=Run(20,{L1})\nrun30=Run(30,0,-{L2})\nrun40=Run(40,-{L3})\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',40)\nanc2.apply([run40])")
        return g, {10:(0,0),20:(L1,0),30:(L1,-L2),40:(L1-L3,-L2)}, ["run20","run30","run40"], [10,40]

    elif config == "Forma Z (offset)":
        g = (f"pt10=Point(10)\nrun20=Run(20,{L1})\nrun30=Run(30,0,-{L2})\nrun40=Run(40,{L3})\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',40)\nanc2.apply([run40])")
        return g, {10:(0,0),20:(L1,0),30:(L1,-L2),40:(L1+L3,-L2)}, ["run20","run30","run40"], [10,40]

    raise ValueError(f"Config desconocida: {config}")


def _geom_vertical(config, L1, L2, L3):
    """
    Sistema vertical: el caño principal sube en +Y.
    Las ramas horizontales van en +X.
    Gravedad sigue en -Y → peso causa compresión axial en tramos verticales.
    """
    if config == "Voladizo (1 apoyo empotrado)":
        # Sube recto, apoyo en la base
        g = (f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])")
        return g, {10:(0,0),20:(0,L1)}, ["run20"], [10]

    elif config == "Simplemente apoyado (2 apoyos)":
        # Sube recto, apoyos arriba y abajo
        g = (f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',20)\nanc2.apply([run20])")
        return g, {10:(0,0),20:(0,L1)}, ["run20"], [10,20]

    elif config == "Forma L (codo 90°)":
        # Sube en Y, luego brazo horizontal en +X
        g = (f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\nrun30=Run(30,{L2},0,0)\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',30)\nanc2.apply([run30])")
        return g, {10:(0,0),20:(0,L1),30:(L2,L1)}, ["run20","run30"], [10,30]

    elif config == "Forma U (lazo de expansión)":
        # Sube, brazo derecho, baja  → herradura
        g = (f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\nrun30=Run(30,{L2},0,0)\nrun40=Run(40,0,-{L3},0)\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',40)\nanc2.apply([run40])")
        return g, {10:(0,0),20:(0,L1),30:(L2,L1),40:(L2,L1-L3)}, ["run20","run30","run40"], [10,40]

    elif config == "Forma Z (offset)":
        # Sube, brazo derecho, sube de nuevo → escalón
        g = (f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\nrun30=Run(30,{L2},0,0)\nrun40=Run(40,0,{L3},0)\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',40)\nanc2.apply([run40])")
        return g, {10:(0,0),20:(0,L1),30:(L2,L1),40:(L2,L1+L3)}, ["run20","run30","run40"], [10,40]

    raise ValueError(f"Config desconocida: {config}")


# ══════════════════════════════════════════════════════════
# SCRIPT PSI
# ══════════════════════════════════════════════════════════

def build_psi_script(cfg):
    orientation = cfg["orientation"]
    is_planta   = "planta" in orientation

    vertical_line = "mdl.settings.vertical='z'" if is_planta else ""
    header = PSI_HEADER.format(
        size=cfg["size"], sched=cfg["sched"],
        vertical_line=vertical_line)

    geom, nodes, elems, anchors = build_geometry(
        cfg["config"], cfg["L1_in"], cfg["L2_in"], cfg["L3_in"], orientation)

    elems_str = ", ".join(elems)
    loads = lcs = ""
    lc_names = []

    if cfg["use_weight"]:
        loads += f"w1=Weight('W1',1)\nw1.apply([{elems_str}])\n"
        lcs   += f"lc_w=LoadCase('l1','sus',[Weight],[1])\n"
        lc_names.append("lc_w")

    if cfg["use_thermal"]:
        loads += f"t1=Thermal('T1',1,{cfg['T_op']},{cfg['T_ins']})\nt1.apply([{elems_str}])\n"
        lcs   += f"lc_t=LoadCase('l2','exp',[Thermal],[1])\n"
        lc_names.append("lc_t")

    footer = (f"b311=B31167('B31.1')\nb311.apply([{elems_str}])\n"
              f"mdl.analyze()\n"
              f"disp=Movements('r1',[{','.join(lc_names)}])\ndisp.to_screen()\n")

    return header + geom + "\n" + loads + lcs + footer, nodes, anchors


# ══════════════════════════════════════════════════════════
# EJECUCIÓN PSI
# ══════════════════════════════════════════════════════════

def run_psi(script_text):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(script_text); fname = f.name
    try:
        r = subprocess.run([sys.executable, fname],
                           capture_output=True, text=True, timeout=90)
        return r.stdout, r.stderr, r.returncode
    finally:
        os.unlink(fname)


def parse_movements(stdout, use_weight, use_thermal):
    results = {}
    lines = stdout.splitlines()
    multi = "MULTIPLE LOAD CASES" in stdout

    if multi:
        in_tbl = False; cur_n = None
        for line in lines:
            if "TRANSLATIONS" in line and "ROTATIONS" in line:
                in_tbl = True; continue
            if not in_tbl: continue
            m = re.match(
                r"\s*(\d+)\s+(l\d+)\s*\(\s*(\w+)\s*\)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m:
                cur_n = int(m.group(1))
                key = "Peso" if m.group(3).lower()=="sus" else "Térmica"
                results.setdefault(cur_n,{})[key] = (
                    float(m.group(4)), float(m.group(5)), float(m.group(6)))
                continue
            m2 = re.match(
                r"\s+(l\d+)\s*\(\s*(\w+)\s*\)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m2 and cur_n is not None:
                key = "Peso" if m2.group(2).lower()=="sus" else "Térmica"
                results.setdefault(cur_n,{})[key] = (
                    float(m2.group(3)), float(m2.group(4)), float(m2.group(5)))
    else:
        single_key = "Peso" if use_weight else "Térmica"
        in_tbl = False
        for line in lines:
            if re.match(r"\s*NODE\s+DX\s+DY", line):
                in_tbl = True; continue
            if not in_tbl: continue
            m = re.match(r"\s*(\d+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m:
                results.setdefault(int(m.group(1)),{})[single_key] = (
                    float(m.group(2)), float(m.group(3)), float(m.group(4)))
    return results


# ══════════════════════════════════════════════════════════
# VISUALIZACIÓN
# ══════════════════════════════════════════════════════════

def _disp_xy(node, key, movements, orientation):
    """
    Devuelve (ddx, ddy) en pies para plotear según orientación.
    - Horizontal/Vertical : usa DX, DY del resultado PSI
    - En planta            : usa DX (=X real), DY (=Y real)
                             el DZ (peso) no se muestra en 2D
    """
    is_planta = "planta" in orientation
    if node not in movements or key not in movements[node]:
        return 0, 0
    dx, dy, dz = movements[node][key]
    if is_planta and key == "Peso":
        # Peso deflecta en Z → fuera del plano 2D → no mover el punto
        return 0, 0
    return dx / 12, dy / 12   # pulgadas → pies


def make_figure(nodes, anchors, movements, scale, orientation, config):
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    nids = sorted(nodes.keys())
    xs0 = [nodes[n][0]/12 for n in nids]
    ys0 = [nodes[n][1]/12 for n in nids]

    # ── Geometría original ──────────────────────────────
    ax.plot(xs0, ys0, color=PIPE_COL, linewidth=5,
            solid_capstyle='round', solid_joinstyle='round',
            zorder=3, label="Geometría original")
    for n, x, y in zip(nids, xs0, ys0):
        ax.plot(x, y, 'o', color=NODE_COL, markersize=8,
                markeredgecolor=BG, markeredgewidth=1.5, zorder=5)
        ax.annotate(f" {n}", (x, y), color=SUBTEXT, fontsize=9,
                    va='center', fontfamily='monospace', zorder=6)
    for n in anchors:
        _draw_anchor(ax, nodes[n][0]/12, nodes[n][1]/12)

    # ── Deformadas ──────────────────────────────────────
    is_planta = "planta" in orientation
    for key, color, ls, lbl in [
        ("Peso",    DEFORM_W, "--",  "Deformada — Peso propio"),
        ("Térmica", DEFORM_T, "-.",  "Deformada — Expansión térmica"),
    ]:
        has = any(key in movements.get(n, {}) for n in nids)
        if not has:
            continue

        # En planta + Peso: deflexión en Z, no visible en 2D → skip curva
        if is_planta and key == "Peso":
            continue

        xsd, ysd = [], []
        for n, x0, y0 in zip(nids, xs0, ys0):
            ddx, ddy = _disp_xy(n, key, movements, orientation)
            xsd.append(x0 + ddx * scale)
            ysd.append(y0 + ddy * scale)

        ax.plot(xsd, ysd, color=color, linewidth=2.5, linestyle=ls,
                solid_capstyle='round', solid_joinstyle='round',
                label=f"{lbl}  (×{scale})", zorder=4)
        for x, y in zip(xsd, ysd):
            ax.plot(x, y, 'o', color=color, markersize=5,
                    markeredgecolor=BG, markeredgewidth=1, zorder=6)

        _annotate_max(ax, nids, nodes, movements, key, color, scale, orientation)

    # ── Flecha de gravedad ──────────────────────────────
    _draw_gravity_arrow(ax, orientation)

    # ── Ejes ────────────────────────────────────────────
    is_vertical = "Vertical" in orientation
    ax.set_xlabel("X  (ft)" if not is_vertical else "X lateral  (ft)",
                  color=SUBTEXT, fontsize=10, fontfamily='monospace')
    ax.set_ylabel("Y  (ft)" if not is_planta else "Y  (ft)  — Vista de planta",
                  color=SUBTEXT, fontsize=10, fontfamily='monospace')

    ax.set_aspect('equal', 'datalim')
    ax.margins(0.28)
    ax.tick_params(colors=SUBTEXT, labelsize=9)
    for sp in ax.spines.values(): sp.set_edgecolor(BORDER)
    ax.grid(True, color=GRID_COL, linewidth=0.8, alpha=0.9, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc='best', fontsize=9, facecolor=PANEL2,
              edgecolor=BORDER, labelcolor=NODE_COL, framealpha=0.92)

    # Nota para en planta
    if is_planta:
        ax.text(0.99, 0.02,
                "⊗  Gravedad perpendicular al plano (-Z)\n"
                "   Deflexión por peso fuera del plano — no mostrada",
                transform=ax.transAxes, ha='right', va='bottom',
                color=GRAV_COL, fontsize=8, fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.4', facecolor=BG,
                          edgecolor=GRAV_COL, alpha=0.85))

    fig.tight_layout()
    return fig


def _draw_anchor(ax, x, y):
    s = 0.22
    tri = plt.Polygon([[x,y],[x-s,y-s*1.2],[x+s,y-s*1.2]],
                      color=ANCHOR_COL, zorder=7, alpha=0.85)
    ax.add_patch(tri)
    ax.plot([x-s*1.3, x+s*1.3], [y-s*1.2, y-s*1.2],
            color=ANCHOR_COL, linewidth=2.5, zorder=7)
    for i in range(5):
        ox = -s*1.2 + i*(s*0.6)
        ax.plot([x+ox, x+ox-s*0.4], [y-s*1.2, y-s*1.7],
                color=ANCHOR_COL, linewidth=1, alpha=0.5, zorder=7)


def _draw_gravity_arrow(ax, orientation):
    """Dibuja una flecha o símbolo indicando la dirección de la gravedad."""
    is_planta = "planta" in orientation
    # Posición: esquina superior izquierda del área de datos
    xmin, xmax = ax.get_xlim() if ax.get_xlim() != (0,1) else (0, 1)
    ymin, ymax = ax.get_ylim() if ax.get_ylim() != (0,1) else (0, 1)

    # Usamos coordenadas de ejes (0-1) para que no dependa del zoom
    if is_planta:
        # Símbolo ⊗ (gravedad entrando a la pantalla)
        ax.text(0.04, 0.97, "⊗  g",
                transform=ax.transAxes, ha='left', va='top',
                color=GRAV_COL, fontsize=12, fontweight='bold',
                fontfamily='monospace', zorder=10)
    else:
        # Flecha apuntando hacia abajo
        ax.annotate("", xy=(0.04, 0.82), xytext=(0.04, 0.97),
                    xycoords='axes fraction', textcoords='axes fraction',
                    arrowprops=dict(arrowstyle='->', color=GRAV_COL,
                                   lw=2.5), zorder=10)
        ax.text(0.06, 0.895, "g",
                transform=ax.transAxes, ha='left', va='center',
                color=GRAV_COL, fontsize=11, fontweight='bold',
                fontfamily='monospace', zorder=10)


def _annotate_max(ax, nids, nodes, movements, key, color, scale, orientation):
    best_mag, best_n = 0, None
    for n in nids:
        if n in movements and key in movements[n]:
            ddx, ddy = _disp_xy(n, key, movements, orientation)
            mag = (ddx**2 + ddy**2)**0.5
            if mag > best_mag:
                best_mag, best_n = mag, n
    if best_n is None or best_mag < 1e-6:
        return
    ddx, ddy = _disp_xy(best_n, key, movements, orientation)
    ox = nodes[best_n][0]/12 + ddx * scale
    oy = nodes[best_n][1]/12 + ddy * scale
    # Real magnitude (all components)
    dx, dy, dz = movements[best_n][key]
    real_mag = (dx**2 + dy**2 + dz**2)**0.5
    ax.annotate(f"  Δmax={real_mag:.3f}\"", (ox, oy), color=color,
                fontsize=9, fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=BG,
                          edgecolor=color, alpha=0.9), zorder=8)


# ══════════════════════════════════════════════════════════
# TABLA
# ══════════════════════════════════════════════════════════

def build_dataframe(nodes, movements, orientation):
    is_planta = "planta" in orientation
    rows = []
    for n in sorted(nodes.keys()):
        for key in ["Peso", "Térmica"]:
            if n not in movements or key not in movements[n]:
                continue
            dx, dy, dz = movements[n][key]
            mag = (dx**2 + dy**2 + dz**2)**0.5
            nota = ""
            if is_planta and key == "Peso":
                nota = "⊗ fuera del plano"
            rows.append({
                "Nodo": n,
                "Carga": key,
                "DX (in)": round(dx, 4),
                "DY (in)": round(dy, 4),
                "DZ (in)": round(dz, 4),
                "|D| (in)": round(mag, 4),
                "Nota": nota,
            })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════
# STREAMLIT APP
# ══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="PSI Simulator",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #1e2530;
    border-right: 2px solid #3a7bd5;
}
[data-testid="stSidebar"] * { color: #f0f4ff !important; }
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] .stMarkdown h2 {
    color: #7dd3fc !important;
    font-size: 0.85rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-top: 1.1rem;
    margin-bottom: 0.2rem;
}
[data-testid="stSidebar"] hr { border-color: #3a4a6b !important; }
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stNumberInput input {
    background-color: #2a3347 !important;
    color: #f0f4ff !important;
    border: 1px solid #4a6090 !important;
    border-radius: 6px;
}
[data-testid="stSidebar"] label { color: #c8d8f0 !important; font-weight: 500; }
[data-testid="stSidebar"] .stCheckbox label { color: #f0f4ff !important; }
[data-testid="stSidebar"] .stCaption { color: #7dd3fc !important; }
/* Main */
h1 { color: #1e3a8a; font-family: monospace; font-size: 1.8rem; }
h2, h3 { color: #1d4ed8; font-family: monospace; }
.stButton > button {
    background-color: #2563eb; color: #ffffff;
    font-weight: bold; font-family: monospace;
    border: none; border-radius: 8px;
    padding: 0.7rem 2rem; font-size: 1rem;
    width: 100%; letter-spacing: 0.05em;
}
.stButton > button:hover { background-color: #1d4ed8; color: #ffffff; }
[data-testid="stMetric"] {
    background-color: #f0f7ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px; padding: 0.5rem 0.8rem;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🔧 PSI Simulator")
    st.markdown("*Pipe Stress Infinity*")
    st.divider()

    st.markdown("### ⚙️ Tipo de sistema")
    config = st.selectbox("Configuración", CONFIGS, index=0,
                          label_visibility="collapsed")

    st.markdown("### 🧭 Orientación")
    orientation = st.selectbox("Orientación", ORIENTATIONS, index=0,
                               label_visibility="collapsed")

    # Pequeño resumen visual de qué significa la orientación
    if "Vertical" in orientation:
        st.caption("↑ Caño principal sube en Y · Gravedad axial al tramo vertical")
    elif "planta" in orientation:
        st.caption("⊗ Vista de planta · Gravedad perpendicular al plano")
    else:
        st.caption("→ Caño corre en X · Gravedad deflecta hacia abajo")

    st.markdown("### 🔩 Tubería")
    col1, col2 = st.columns(2)
    with col1:
        size  = st.selectbox("NPS (in)", PIPE_SIZES, index=3)
    with col2:
        sched = st.selectbox("Sched.", SCHEDULES, index=2)
    st.caption("Material: A53A Gr.A (B31.1)")

    st.markdown("### 📐 Geometría (pies)")
    L1 = st.number_input("Longitud L1", min_value=1.0, max_value=200.0, value=10.0, step=0.5)

    needs_L2 = config not in ("Voladizo (1 apoyo empotrado)",
                               "Simplemente apoyado (2 apoyos)")
    needs_L3 = config in ("Forma U (lazo de expansión)", "Forma Z (offset)")

    L2 = st.number_input("Longitud L2", min_value=1.0, max_value=200.0,
                         value=8.0, step=0.5, disabled=not needs_L2)
    L3 = st.number_input("Longitud L3", min_value=1.0, max_value=200.0,
                         value=10.0, step=0.5, disabled=not needs_L3)

    st.markdown("### 📦 Cargas")
    use_weight  = st.checkbox("Peso propio (gravedad)", value=True)
    use_thermal = st.checkbox("Expansión térmica", value=True)

    if use_thermal:
        col3, col4 = st.columns(2)
        with col3:
            T_op  = st.number_input("T op. (°F)",  value=400, step=10)
        with col4:
            T_ins = st.number_input("T inst. (°F)", value=70,  step=5)
    else:
        T_op, T_ins = 400, 70

    st.markdown("### 🔍 Visualización")
    scale = st.slider("Ampliación deformada", min_value=1, max_value=500,
                      value=50, step=5)

    st.divider()
    run_btn = st.button("▶  ANALIZAR", use_container_width=True)

# ── Panel principal ───────────────────────────────────────
st.markdown("# Pipe Stress Infinity — Simulador Visual")
orient_short = orientation.split("—")[0].strip()
st.markdown(
    f"**Configuración:** {config} &nbsp;|&nbsp; "
    f"**NPS {size}\"  Sch.{sched}** &nbsp;|&nbsp; "
    f"A53A / B31.1 &nbsp;|&nbsp; **Orientación:** {orient_short}")
st.divider()

if not run_btn:
    st.info("👈  Configurá los parámetros en el panel izquierdo y presioná **▶ ANALIZAR**.")
    st.stop()

if not use_weight and not use_thermal:
    st.error("Seleccioná al menos una carga (peso propio o expansión térmica).")
    st.stop()

# ── Construir y correr ────────────────────────────────────
cfg = {
    "config":      config,
    "orientation": orientation,
    "size":        size,
    "sched":       sched,
    "L1_in":       L1 * 12,
    "L2_in":       L2 * 12,
    "L3_in":       L3 * 12,
    "use_weight":  use_weight,
    "use_thermal": use_thermal,
    "T_op":        T_op,
    "T_ins":       T_ins,
    "scale":       scale,
}

with st.spinner("⏳ Ejecutando análisis PSI..."):
    try:
        script, nodes, anchors = build_psi_script(cfg)
        stdout, stderr, rc = run_psi(script)
    except Exception as e:
        st.error(f"Error al ejecutar PSI: {e}")
        st.stop()

if rc != 0 or ("TRANSLATIONS" not in stdout and "MOVEMENTS" not in stdout):
    st.error("PSI no completó el análisis.")
    with st.expander("Ver log de error", expanded=True):
        st.code(stderr[-2000:] + "\n\n--- STDOUT ---\n" + stdout, language="text")
    st.stop()

movements = parse_movements(stdout, use_weight, use_thermal)
if not movements:
    st.error("No se obtuvieron desplazamientos.")
    st.stop()

# ── Métricas ─────────────────────────────────────────────
st.markdown("### 📊 Resultados")
is_planta = "planta" in orientation
cols_m = st.columns(4)

for key, label, col in [
    ("Peso",    "🟠 Peso propio",       cols_m[0]),
    ("Térmica", "🔴 Expansión térmica", cols_m[1]),
]:
    vals = [(dx**2+dy**2+dz**2)**0.5
            for nd in movements.values()
            if key in nd
            for dx, dy, dz in [nd[key]]]
    if vals:
        note = "Δ máximo (fuera del plano)" if (is_planta and key=="Peso") else "Δ máximo"
        col.metric(label, f"{max(vals):.4f} \"", note)

max_all = max(
    (dx**2+dy**2+dz**2)**0.5
    for nd in movements.values()
    for dx, dy, dz in nd.values()
)
cols_m[2].metric("🔵 Δ total máximo", f"{max_all:.4f} \"", "todas las cargas")
cols_m[3].metric("📍 Nodos", len(nodes))

st.divider()

# ── Gráfico ──────────────────────────────────────────────
st.markdown("### 🖼️ Visualización")
fig = make_figure(nodes, anchors, movements, scale, orientation, config)
st.pyplot(fig, use_container_width=True)
plt.close(fig)

# ── Tabla ────────────────────────────────────────────────
st.markdown("### 📋 Tabla de desplazamientos  (pulgadas)")
df = build_dataframe(nodes, movements, orientation)

def color_row(row):
    c = "#f0883e22" if row["Carga"] == "Peso" else "#ff7b7222"
    return [f"background-color: {c}"] * len(row)

fmt = {"DX (in)":"{:+.4f}", "DY (in)":"{:+.4f}",
       "DZ (in)":"{:+.4f}", "|D| (in)":"{:.4f}"}
st.dataframe(df.style.apply(color_row, axis=1).format(fmt),
             use_container_width=True, hide_index=True)

# ── Log PSI ──────────────────────────────────────────────
with st.expander("📄 Ver log de PSI"):
    st.code(stdout, language="text")
