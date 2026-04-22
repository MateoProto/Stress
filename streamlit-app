"""
Pipe Stress Infinity — Simulador Visual (Streamlit)
"""

# ── Parche automático PSI/NumPy (se aplica al arrancar) ──
import os, sys
def _patch_psi():
    try:
        import psi
        path = os.path.join(os.path.dirname(psi.__file__), 'loads.py')
        with open(path, 'r') as f:
            content = f.read()
        if 'wxl, wyl, wzl = wl\n' in content:
            fixed = content.replace('wxl, wyl, wzl = wl\n', 'wxl, wyl, wzl = wl[:, 0]\n')
            with open(path, 'w') as f:
                f.write(fixed)
    except Exception:
        pass
_patch_psi()
# ─────────────────────────────────────────────────────────

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import subprocess, tempfile, os, re, io
import pandas as pd

# ── Colores ──────────────────────────────────────────────
BG        = "#0d1117"
PIPE_COL  = "#58a6ff"
DEFORM_W  = "#f0883e"
DEFORM_T  = "#ff7b72"
ANCHOR_COL= "#3fb950"
NODE_COL  = "#e6edf3"
SUBTEXT   = "#7d8590"
GRID_COL  = "#21262d"
PANEL2    = "#1c2128"
BORDER    = "#30363d"

PIPE_SIZES = ["2","3","4","6","8","10","12","16"]
SCHEDULES  = ["10","20","40","80","160"]
CONFIGS    = [
    "Voladizo (1 apoyo empotrado)",
    "Simplemente apoyado (2 apoyos)",
    "Forma L (codo 90°)",
    "Forma U (lazo de expansión)",
    "Forma Z (offset)",
]

PSI_HEADER = """
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
pipe1 = Pipe.from_file('pipe1', '{size}', '{sched}')
mat1 = Material.from_file('mat1', 'A53A', 'B31.1')
"""

def build_geometry(config, L1, L2, L3):
    if config == "Voladizo (1 apoyo empotrado)":
        geom = f"pt10=Point(10)\nrun20=Run(20,{L1})\nanc1=Anchor('A1',10)\nanc1.apply([run20])\n"
        return geom, {10:(0,0),20:(L1,0)}, ["run20"], [10]
    elif config == "Simplemente apoyado (2 apoyos)":
        geom = f"pt10=Point(10)\nrun20=Run(20,{L1})\nanc1=Anchor('A1',10)\nanc1.apply([run20])\nanc2=Anchor('A2',20)\nanc2.apply([run20])\n"
        return geom, {10:(0,0),20:(L1,0)}, ["run20"], [10,20]
    elif config == "Forma L (codo 90°)":
        geom = f"pt10=Point(10)\nrun20=Run(20,{L1})\nrun30=Run(30,0,-{L2})\nanc1=Anchor('A1',10)\nanc1.apply([run20])\nanc2=Anchor('A2',30)\nanc2.apply([run30])\n"
        return geom, {10:(0,0),20:(L1,0),30:(L1,-L2)}, ["run20","run30"], [10,30]
    elif config == "Forma U (lazo de expansión)":
        geom = f"pt10=Point(10)\nrun20=Run(20,{L1})\nrun30=Run(30,0,-{L2})\nrun40=Run(40,-{L3})\nanc1=Anchor('A1',10)\nanc1.apply([run20])\nanc2=Anchor('A2',40)\nanc2.apply([run40])\n"
        return geom, {10:(0,0),20:(L1,0),30:(L1,-L2),40:(L1-L3,-L2)}, ["run20","run30","run40"], [10,40]
    elif config == "Forma Z (offset)":
        geom = f"pt10=Point(10)\nrun20=Run(20,{L1})\nrun30=Run(30,0,-{L2})\nrun40=Run(40,{L3})\nanc1=Anchor('A1',10)\nanc1.apply([run20])\nanc2=Anchor('A2',40)\nanc2.apply([run40])\n"
        return geom, {10:(0,0),20:(L1,0),30:(L1,-L2),40:(L1+L3,-L2)}, ["run20","run30","run40"], [10,40]
    raise ValueError(f"Config desconocida: {config}")

def build_psi_script(cfg):
    geom, nodes, elems, anchors = build_geometry(cfg["config"], cfg["L1_in"], cfg["L2_in"], cfg["L3_in"])
    elems_str = ", ".join(elems)
    header = PSI_HEADER.format(size=cfg["size"], sched=cfg["sched"])
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
    return header + geom + loads + lcs + footer, nodes, anchors

def run_psi(script_text):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.inp', delete=False, dir='/tmp') as f:
        f.write(script_text); fname = f.name
    try:
        r = subprocess.run(['psi', fname], capture_output=True, text=True, timeout=90)
        return r.stdout, r.stderr
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
            m = re.match(r"\s*(\d+)\s+(l\d+)\s*\(\s*(\w+)\s*\)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m:
                cur_n = int(m.group(1))
                key = "Peso" if m.group(3).lower()=="sus" else "Térmica"
                results.setdefault(cur_n,{})[key] = (float(m.group(4)),float(m.group(5)),float(m.group(6)))
                continue
            m2 = re.match(r"\s+(l\d+)\s*\(\s*(\w+)\s*\)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m2 and cur_n is not None:
                key = "Peso" if m2.group(2).lower()=="sus" else "Térmica"
                results.setdefault(cur_n,{})[key] = (float(m2.group(3)),float(m2.group(4)),float(m2.group(5)))
    else:
        single_key = "Peso" if use_weight else "Térmica"
        in_tbl = False
        for line in lines:
            if re.match(r"\s*NODE\s+DX\s+DY", line):
                in_tbl = True; continue
            if not in_tbl: continue
            m = re.match(r"\s*(\d+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m:
                results.setdefault(int(m.group(1)),{})[single_key] = (float(m.group(2)),float(m.group(3)),float(m.group(4)))
    return results

def make_figure(nodes, anchors, movements, scale):
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    nids = sorted(nodes.keys())
    xs0  = [nodes[n][0]/12 for n in nids]
    ys0  = [nodes[n][1]/12 for n in nids]

    ax.plot(xs0, ys0, color=PIPE_COL, linewidth=5,
            solid_capstyle='round', solid_joinstyle='round',
            zorder=3, label="Geometría original")
    for n,x,y in zip(nids,xs0,ys0):
        ax.plot(x,y,'o',color=NODE_COL,markersize=8,
                markeredgecolor=BG,markeredgewidth=1.5,zorder=5)
        ax.annotate(f" {n}",(x,y),color=SUBTEXT,fontsize=9,
                    va='center',fontfamily='monospace',zorder=6)
    for n in anchors:
        _draw_anchor(ax, nodes[n][0]/12, nodes[n][1]/12)

    for key, color, ls, lbl in [
        ("Peso",    DEFORM_W, "--",  "Deformada — Peso propio"),
        ("Térmica", DEFORM_T, "-.",  "Deformada — Expansión térmica"),
    ]:
        if not any(key in movements.get(n,{}) for n in nids): continue
        xsd,ysd=[],[]
        for n,x0,y0 in zip(nids,xs0,ys0):
            if n in movements and key in movements[n]:
                dx,dy,_ = movements[n][key]
                xsd.append(x0+dx*scale/12); ysd.append(y0+dy*scale/12)
            else:
                xsd.append(x0); ysd.append(y0)
        ax.plot(xsd,ysd,color=color,linewidth=2.5,linestyle=ls,
                solid_capstyle='round',solid_joinstyle='round',
                label=f"{lbl}  (×{scale})",zorder=4)
        for x,y in zip(xsd,ysd):
            ax.plot(x,y,'o',color=color,markersize=5,
                    markeredgecolor=BG,markeredgewidth=1,zorder=6)
        # Max displacement annotation
        best_mag,best_n=0,None
        for n in nids:
            if n in movements and key in movements[n]:
                dx,dy,dz=movements[n][key]
                mag=(dx**2+dy**2+dz**2)**0.5
                if mag>best_mag: best_mag,best_n=mag,n
        if best_n and best_mag>0.001:
            dx,dy,_=movements[best_n][key]
            ox=nodes[best_n][0]/12+dx*scale/12
            oy=nodes[best_n][1]/12+dy*scale/12
            ax.annotate(f"  Δmax={best_mag:.3f}\"",(ox,oy),color=color,
                        fontsize=9,fontfamily='monospace',
                        bbox=dict(boxstyle='round,pad=0.3',facecolor=BG,
                                  edgecolor=color,alpha=0.9),zorder=8)

    ax.set_aspect('equal','datalim')
    ax.margins(0.25)
    ax.set_xlabel("X  (ft)",color=SUBTEXT,fontsize=10,fontfamily='monospace')
    ax.set_ylabel("Y  (ft)",color=SUBTEXT,fontsize=10,fontfamily='monospace')
    ax.tick_params(colors=SUBTEXT,labelsize=9)
    for sp in ax.spines.values(): sp.set_edgecolor(BORDER)
    ax.grid(True,color=GRID_COL,linewidth=0.8,alpha=0.9,zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc='best',fontsize=9,facecolor=PANEL2,
              edgecolor=BORDER,labelcolor=NODE_COL,framealpha=0.92)
    fig.tight_layout()
    return fig

def _draw_anchor(ax, x, y):
    s = 0.22
    tri = plt.Polygon([[x,y],[x-s,y-s*1.2],[x+s,y-s*1.2]],
                      color=ANCHOR_COL,zorder=7,alpha=0.85)
    ax.add_patch(tri)
    ax.plot([x-s*1.3,x+s*1.3],[y-s*1.2,y-s*1.2],
            color=ANCHOR_COL,linewidth=2.5,zorder=7)
    for i in range(5):
        ox=-s*1.2+i*(s*0.6)
        ax.plot([x+ox,x+ox-s*0.4],[y-s*1.2,y-s*1.7],
                color=ANCHOR_COL,linewidth=1,alpha=0.5,zorder=7)

def build_dataframe(nodes, movements):
    rows = []
    for n in sorted(nodes.keys()):
        for key in ["Peso","Térmica"]:
            if n not in movements or key not in movements[n]: continue
            dx,dy,dz = movements[n][key]
            mag = (dx**2+dy**2+dz**2)**0.5
            rows.append({
                "Nodo": n,
                "Carga": key,
                "DX (in)": round(dx,4),
                "DY (in)": round(dy,4),
                "DZ (in)": round(dz,4),
                "|D| (in)": round(mag,4),
            })
    return pd.DataFrame(rows)

# ── Streamlit App ─────────────────────────────────────────

st.set_page_config(
    page_title="PSI Simulator",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { background-color: #161b22; }
[data-testid="stSidebar"] label { color: #e6edf3 !important; }
.stSelectbox label, .stNumberInput label, .stCheckbox label { color: #e6edf3; }
h1 { color: #58a6ff; font-family: 'Courier New', monospace; }
h2, h3 { color: #3fb950; font-family: 'Courier New', monospace; }
.stButton > button {
    background-color: #58a6ff;
    color: #0d1117;
    font-weight: bold;
    font-family: 'Courier New', monospace;
    border: none;
    padding: 0.6rem 2rem;
    font-size: 1rem;
    width: 100%;
}
.stButton > button:hover { background-color: #388bfd; color: #0d1117; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🔧 PSI Simulator")
    st.markdown("*Pipe Stress Infinity*")
    st.divider()

    st.markdown("### ⚙️ Tipo de sistema")
    config = st.selectbox("Configuración", CONFIGS, index=0, label_visibility="collapsed")

    st.markdown("### 🔩 Tubería")
    col1, col2 = st.columns(2)
    with col1:
        size  = st.selectbox("NPS (in)", PIPE_SIZES, index=3)
    with col2:
        sched = st.selectbox("Sched.", SCHEDULES, index=2)
    st.caption("Material: A53A Gr.A (B31.1)")

    st.markdown("### 📐 Geometría (pies)")
    L1 = st.number_input("Longitud L1", min_value=1.0, max_value=200.0, value=10.0, step=0.5)

    needs_L2 = config not in ("Voladizo (1 apoyo empotrado)", "Simplemente apoyado (2 apoyos)")
    needs_L3 = config in ("Forma U (lazo de expansión)", "Forma Z (offset)")

    L2 = st.number_input("Longitud L2", min_value=1.0, max_value=200.0, value=8.0, step=0.5,
                         disabled=not needs_L2)
    L3 = st.number_input("Longitud L3", min_value=1.0, max_value=200.0, value=10.0, step=0.5,
                         disabled=not needs_L3)

    st.markdown("### 📦 Cargas")
    use_weight  = st.checkbox("Peso propio (gravedad)", value=True)
    use_thermal = st.checkbox("Expansión térmica", value=True)

    if use_thermal:
        col3, col4 = st.columns(2)
        with col3:
            T_op  = st.number_input("T operación (°F)", value=400, step=10)
        with col4:
            T_ins = st.number_input("T instalación (°F)", value=70, step=5)
    else:
        T_op, T_ins = 400, 70

    st.markdown("### 🔍 Visualización")
    scale = st.slider("Ampliación deformada", min_value=1, max_value=500, value=50, step=5)

    st.divider()
    run_btn = st.button("▶  ANALIZAR", use_container_width=True)

# ── Main panel ───────────────────────────────────────────
st.markdown("# Pipe Stress Infinity — Simulador Visual")
st.markdown(f"**Configuración:** {config} &nbsp;|&nbsp; **NPS {size}\"  Sch.{sched}** &nbsp;|&nbsp; A53A / B31.1")
st.divider()

if not run_btn:
    st.info("👈  Configurá los parámetros en el panel izquierdo y presioná **▶ ANALIZAR**.")
    st.stop()

if not use_weight and not use_thermal:
    st.error("Seleccioná al menos una carga (peso propio o expansión térmica).")
    st.stop()

# Build and run
cfg = {
    "config": config, "size": size, "sched": sched,
    "L1_in": L1*12, "L2_in": L2*12, "L3_in": L3*12,
    "use_weight": use_weight, "use_thermal": use_thermal,
    "T_op": T_op, "T_ins": T_ins, "scale": scale,
}

with st.spinner("⏳ Ejecutando análisis PSI..."):
    try:
        script, nodes, anchors = build_psi_script(cfg)
        stdout, stderr = run_psi(script)
    except Exception as e:
        st.error(f"Error al ejecutar PSI: {e}")
        st.stop()

if "Analysis complete" not in stdout:
    st.error("PSI no completó el análisis.")
    with st.expander("Ver log de error"):
        st.code(stderr + stdout, language="text")
    st.stop()

movements = parse_movements(stdout, use_weight, use_thermal)
if not movements:
    st.error("No se obtuvieron desplazamientos.")
    st.stop()

# ── Métricas rápidas ─────────────────────────────────────
st.markdown("### 📊 Resultados")
cols_m = st.columns(4)
for key, color_label, col in [("Peso","🟠 Peso propio",cols_m[0]),
                               ("Térmica","🔴 Expansión térmica",cols_m[1])]:
    vals = [(dx**2+dy**2)**0.5
            for nd in movements.values()
            if key in nd
            for dx,dy,dz in [nd[key]]]
    if vals:
        col.metric(f"{color_label}", f"{max(vals):.4f} \"", "Δ máximo")

max_all = max(
    (dx**2+dy**2+dz**2)**0.5
    for nd in movements.values()
    for dx,dy,dz in nd.values()
)
cols_m[2].metric("🔵 Δ total máximo", f"{max_all:.4f} \"", "todas las cargas")
cols_m[3].metric("📍 Nodos analizados", len(nodes))

st.divider()

# ── Gráfico ──────────────────────────────────────────────
st.markdown("### 🖼️ Visualización")
fig = make_figure(nodes, anchors, movements, scale)
st.pyplot(fig, use_container_width=True)
plt.close(fig)

# ── Tabla ────────────────────────────────────────────────
st.markdown("### 📋 Tabla de desplazamientos")
df = build_dataframe(nodes, movements)

def color_row(row):
    color = "#f0883e22" if row["Carga"] == "Peso" else "#ff7b7222"
    return [f"background-color: {color}"] * len(row)

st.dataframe(
    df.style.apply(color_row, axis=1).format({
        "DX (in)": "{:+.4f}", "DY (in)": "{:+.4f}",
        "DZ (in)": "{:+.4f}", "|D| (in)": "{:.4f}"
    }),
    use_container_width=True,
    hide_index=True,
)

# ── Log PSI ──────────────────────────────────────────────
with st.expander("📄 Ver log de PSI"):
    st.code(stdout, language="text")
