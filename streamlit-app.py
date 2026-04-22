"""
Pipe Stress Infinity — Simulador Visual (Streamlit)
"""
import os, sys, re, tempfile, subprocess
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
 
# ── Colores ───────────────────────────────────────────────
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
TEXT       = "#e6edf3"
 
# ── Datos constantes ─────────────────────────────────────
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
 
# Material: (nombre display, id CSV, descripción)
PRESET_MATERIALS = [
    ("A53A  — Acero al carbono (ASTM A53 Gr.A)",  "A53A",  0.2830, 0.3, 6.07e-6, 27.9e6, 12000),
    ("A106B — Acero al carbono (ASTM A106 Gr.B)", "A106B", 0.2830, 0.3, 6.07e-6, 27.9e6, 17100),
    ("SS304 — Acero inoxidable 304 (A312 TP304)", "SS304", 0.2900, 0.3, 9.60e-6, 28.0e6, 20000),
    ("SS316 — Acero inoxidable 316 (A312 TP316)", "SS316", 0.2900, 0.3, 9.60e-6, 28.0e6, 20000),
    ("✏️  Material personalizado",                "CUSTOM", 0.2830, 0.3, 6.07e-6, 27.9e6, 15000),
]
MAT_NAMES = [m[0] for m in PRESET_MATERIALS]
 
# ── CSV de materiales con tablas desde -325°F ────────────
# (extender desde bajas temperaturas evita errores de límite en PSI)
MATERIALS_CSV = '''\
name,code,rho,nu,temp,alp,ymod,sh
A53A,B31.1,0.2830,0.3,"-325,-200,-100,-50,70,100,200,300,400,500,600,650,700,750,800,850,900,950,1000,1050,1100","0.000005,0.00000535,0.0000055,0.0000058,0.00000607,0.00000613,0.00000638,0.0000066,0.00000682,0.00000702,0.00000723,0.00000733,0.00000744,0.00000754,0.00000765,0.00000775,0.00000784,0.00000791,0.00000797,0.00000805,0.00000812","30000000,29500000,29000000,,27900000,,27700000,274000000,27000000,26400000,25700000,,24800000,,23400000,,18500000,,15400000,,13000000","12000,12000,12000,12000,12000,12000,12000,12000,12000,12000,12000,12000,11650,10700,9000,9000,9000,9000,9000,9000,9000"
A106B,B31.1,0.2830,0.3,"-325,-200,-100,-50,70,200,300,400,500,600,700,800,900,1000","0.000005,0.00000535,0.0000055,0.0000058,0.00000607,0.00000638,0.0000066,0.00000682,0.00000702,0.00000723,0.00000744,0.00000765,0.00000784,0.00000797","30000000,29500000,29000000,27900000,27900000,27700000,27400000,27000000,26400000,25700000,24800000,23400000,18500000,15400000","17100,17100,17100,17100,17100,17100,17100,17100,15800,14700,13000,10800,7400,6000"
SS304,B31.1,0.2900,0.3,"-325,-200,-100,-50,70,200,300,400,500,600,700,800,900,1000","0.0000088,0.0000091,0.0000093,0.0000095,0.0000096,0.0000099,0.0000101,0.0000103,0.0000105,0.0000107,0.0000109,0.0000111,0.0000113,0.0000115","28300000,28300000,28100000,28000000,28000000,27700000,27300000,26900000,26200000,25500000,24800000,23900000,22900000,21600000","20000,20000,20000,20000,20000,18800,17600,17100,17000,16200,15200,14200,12100,9000"
SS316,B31.1,0.2900,0.3,"-325,-200,-100,-50,70,200,300,400,500,600,700,800,900,1000","0.0000088,0.0000091,0.0000093,0.0000095,0.0000096,0.0000099,0.0000101,0.0000103,0.0000105,0.0000107,0.0000109,0.0000111,0.0000113,0.0000115","28300000,28300000,28100000,28000000,28000000,27700000,27300000,26900000,26200000,25500000,24800000,23900000,22900000,21600000","20000,20000,20000,20000,20000,20000,18400,17500,17100,16700,16200,14200,11200,9000"
'''
 
def build_materials_csv(custom=None):
    """
    Escribe el CSV de materiales en /tmp e incluye el material
    personalizado si se provee.
    custom = dict con keys: rho, nu, alp, E, sh
    """
    csv = MATERIALS_CSV
    if custom:
        rho = custom["rho"]
        nu  = custom["nu"]
        alp = custom["alp"]
        E   = custom["E"]
        sh  = custom["sh"]
        # Tabla constante desde -325°F a 1100°F (mismos valores en todos los puntos)
        temps  = "-325,-200,-100,-50,70,200,300,400,500,600,700,800,900,1000"
        n = 14
        alp_str  = ",".join([str(alp)] * n)
        ymod_str = ",".join([str(E)] * n)
        sh_str   = ",".join([str(sh)] * n)
        csv += (f'CUSTOM,B31.1,{rho},{nu},'
                f'"{temps}","{alp_str}","{ymod_str}","{sh_str}"\n')
    path = "/tmp/psi_materials.csv"
    with open(path, "w") as f:
        f.write(csv)
    return path
 
# ── PSI Header ───────────────────────────────────────────
PSI_HEADER = """\
import inspect, psi.loads as _pl
_s = inspect.getsource(_pl)
_sf = _s.replace('wxl, wyl, wzl = wl\\n', 'wxl, wyl, wzl = wl[:, 0]\\n')
exec(compile(_sf, _pl.__file__ or '<psi.loads>', 'exec'), _pl.__dict__)
from psi.loads import Weight, Thermal
 
import psi
psi.MATERIAL_DATA_FILE = '{csv_path}'
 
from psi.app import App; app = App()
from psi.model import Model
from psi.elements import Run
from psi.sections import Pipe
from psi.material import Material
from psi.loads import Weight, Thermal, Pressure
from psi.loadcase import LoadCase
from psi.reports import Movements
from psi.codes.b311 import B31167
from psi.supports import Anchor
from psi.point import Point
 
mdl = Model('sim')
{vertical_line}
pipe1 = Pipe.from_file('pipe1', '{size}', '{sched}')
mat1 = Material.from_file('mat1', '{mat_id}', 'B31.1')
"""
 
# ══════════════════════════════════════════════════════════
# GEOMETRÍA
# ══════════════════════════════════════════════════════════
 
def build_geometry(config, L1, L2, L3, orientation):
    is_vertical = "Vertical" in orientation
    return _geom_vertical(config, L1, L2, L3) if is_vertical \
        else _geom_horizontal(config, L1, L2, L3)
 
def _geom_horizontal(config, L1, L2, L3):
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
    raise ValueError(f"Config: {config}")
 
def _geom_vertical(config, L1, L2, L3):
    if config == "Voladizo (1 apoyo empotrado)":
        g = f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\nanc1=Anchor('A1',10)\nanc1.apply([run20])"
        return g, {10:(0,0),20:(0,L1)}, ["run20"], [10]
    elif config == "Simplemente apoyado (2 apoyos)":
        g = (f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',20)\nanc2.apply([run20])")
        return g, {10:(0,0),20:(0,L1)}, ["run20"], [10,20]
    elif config == "Forma L (codo 90°)":
        g = (f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\nrun30=Run(30,{L2},0,0)\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',30)\nanc2.apply([run30])")
        return g, {10:(0,0),20:(0,L1),30:(L2,L1)}, ["run20","run30"], [10,30]
    elif config == "Forma U (lazo de expansión)":
        g = (f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\nrun30=Run(30,{L2},0,0)\nrun40=Run(40,0,-{L3},0)\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',40)\nanc2.apply([run40])")
        return g, {10:(0,0),20:(0,L1),30:(L2,L1),40:(L2,L1-L3)}, ["run20","run30","run40"], [10,40]
    elif config == "Forma Z (offset)":
        g = (f"pt10=Point(10)\nrun20=Run(20,0,{L1},0)\nrun30=Run(30,{L2},0,0)\nrun40=Run(40,0,{L3},0)\n"
             f"anc1=Anchor('A1',10)\nanc1.apply([run20])\n"
             f"anc2=Anchor('A2',40)\nanc2.apply([run40])")
        return g, {10:(0,0),20:(0,L1),30:(L2,L1),40:(L2,L1+L3)}, ["run20","run30","run40"], [10,40]
    raise ValueError(f"Config: {config}")
 
# ══════════════════════════════════════════════════════════
# SCRIPT PSI
# ══════════════════════════════════════════════════════════
 
def build_psi_script(cfg):
    is_planta   = "planta"   in cfg["orientation"]
    is_vertical = "Vertical" in cfg["orientation"]
    vertical_line = "mdl.settings.vertical='z'" if is_planta else ""
 
    # CSV de materiales
    custom = cfg.get("custom_mat")
    csv_path = build_materials_csv(custom)
 
    header = PSI_HEADER.format(
        csv_path=csv_path,
        size=cfg["size"], sched=cfg["sched"],
        mat_id=cfg["mat_id"],
        vertical_line=vertical_line)
 
    geom, nodes, elems, anchors = build_geometry(
        cfg["config"], cfg["L1_in"], cfg["L2_in"], cfg["L3_in"], cfg["orientation"])
 
    es = ", ".join(elems)
    loads = lcs = ""
    lc_names = []
 
    if cfg["use_weight"] or cfg["use_pressure"]:
        sus_types = []
        if cfg["use_weight"]:
            loads += f"w1=Weight('W1',1)\nw1.apply([{es}])\n"
            sus_types.append("Weight")
        if cfg["use_pressure"]:
            loads += f"p1=Pressure('P1',1,{cfg['pressure']})\np1.apply([{es}])\n"
            sus_types.append("Pressure")
        lcs   += f"lc_w=LoadCase('l1','sus',[{','.join(sus_types)}],[{','.join(['1']*len(sus_types))}])\n"
        lc_names.append("lc_w")
    if cfg["use_thermal"]:
        loads += f"t1=Thermal('T1',1,{cfg['T_op']},{cfg['T_ins']})\nt1.apply([{es}])\n"
        lcs   += f"lc_t=LoadCase('l2','exp',[Thermal],[1])\n"
        lc_names.append("lc_t")
 
    stress_block = """
from psi.units import Units as _Units
_ndof = 6
_pts  = list(app.points)
print("\\n=== PSI_STRESS_DATA ===")
for _lc in [{lc_names_str}]:
    for _el in app.elements:
        _ii = _pts.index(_el.from_point)
        _ij = _pts.index(_el.to_point)
        _fi = _lc.forces.results[_ii*_ndof:_ii*_ndof+_ndof, 0]
        _fj = _lc.forces.results[_ij*_ndof:_ij*_ndof+_ndof, 0]
        with _Units(user_units="code_english"):
            _slp   = _el.code.slp(_el, _lc)
            _shoop = _el.code.shoop(_el, _lc)
            for _pt, _forces in [(_el.from_point, _fi), (_el.to_point, _fj)]:
                _slb = _el.code.slb(_el, _pt, _forces)
                _sl  = _el.code.sl(_el, _lc, _pt, _forces)
                try:
                    _sa  = _el.code.sallow(_el, _lc, _pt, _forces)
                    _rat = _sl/_sa if _sa else 0
                except Exception:
                    _sa, _rat = 0, 0
                print(f"STRESS|{{_lc.name}}|{{_lc.stype}}|{{_pt.name}}|{{_sl:.2f}}|{{_sa:.2f}}|{{_rat:.4f}}|{{_slp:.2f}}|{{_slb:.2f}}|{{_shoop:.2f}}")
print("=== END_STRESS_DATA ===")
""".format(lc_names_str=", ".join(lc_names))
 
    footer = (f"b311=B31167('B31.1')\nb311.apply([{es}])\n"
              f"mdl.analyze()\n"
              f"disp=Movements('r1',[{','.join(lc_names)}])\ndisp.to_screen()\n")
    footer += stress_block
 
    return header + geom + "\n" + loads + lcs + footer, nodes, anchors
 
# ══════════════════════════════════════════════════════════
# EJECUCIÓN PSI
# ══════════════════════════════════════════════════════════
 
def run_psi(script):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(script); fname = f.name
    try:
        r = subprocess.run([sys.executable, fname],
                           capture_output=True, text=True, timeout=90)
        return r.stdout, r.stderr, r.returncode
    finally:
        os.unlink(fname)
 
def parse_movements(stdout, use_weight, use_thermal):
    results = {}
    lines   = stdout.splitlines()
    multi   = "MULTIPLE LOAD CASES" in stdout
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
        key0 = "Peso" if use_weight else "Térmica"
        in_tbl = False
        for line in lines:
            if re.match(r"\s*NODE\s+DX\s+DY", line):
                in_tbl = True; continue
            if not in_tbl: continue
            m = re.match(r"\s*(\d+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m:
                results.setdefault(int(m.group(1)),{})[key0] = (
                    float(m.group(2)),float(m.group(3)),float(m.group(4)))
    return results
 
# ══════════════════════════════════════════════════════════
# VISUALIZACIÓN
# ══════════════════════════════════════════════════════════
 
def _disp_xy(node, key, movements, orientation):
    is_planta = "planta" in orientation
    if node not in movements or key not in movements[node]: return 0,0
    dx,dy,dz = movements[node][key]
    if is_planta and key=="Peso": return 0,0
    return dx/12, dy/12
 
def parse_stresses(stdout):
    """
    Parsea tensiones del bloque PSI_STRESS_DATA.
    Retorna lista de dicts con: lc, stype, node, sl, sallow, ratio, slp, slb, shoop
    Deduplica nodos (un nodo puede aparecer como extremo de 2 elementos → toma el máximo).
    """
    rows = {}
    in_block = False
    for line in stdout.splitlines():
        if "PSI_STRESS_DATA" in line:   in_block = True;  continue
        if "END_STRESS_DATA" in line:   in_block = False; continue
        if not in_block or not line.startswith("STRESS|"): continue
        parts = line.split("|")
        if len(parts) < 10: continue
        _, lc, stype, node, sl, sa, ratio, slp, slb, shoop = parts[:10]
        key = (lc, node)
        row = {"lc": lc, "stype": stype, "node": int(node),
               "sl": float(sl), "sallow": float(sa), "ratio": float(ratio),
               "slp": float(slp), "slb": float(slb), "shoop": float(shoop)}
        # Keep max sl at each node/lc (avoid duplicating shared nodes)
        if key not in rows or float(sl) > rows[key]["sl"]:
            rows[key] = row
    return list(rows.values())
 
 
def make_stress_figure(stress_rows, nodes):
    """Bar chart showing S/Sallow ratio per node, colored by severity."""
    if not stress_rows: return None
 
    # Group by stype
    sus_rows = [r for r in stress_rows if r["stype"] == "sus"]
    exp_rows = [r for r in stress_rows if r["stype"] == "exp"]
 
    n_plots = (1 if sus_rows else 0) + (1 if exp_rows else 0)
    if n_plots == 0: return None
 
    fig, axes = plt.subplots(1, n_plots, figsize=(6*n_plots, max(3, len(nodes)*0.6+1.5)))
    if n_plots == 1: axes = [axes]
    fig.patch.set_facecolor(BG)
 
    for ax, rows, title in zip(axes,
                                [r for r in [sus_rows, exp_rows] if r],
                                ["Carga sostenida (Peso + Presión)",
                                 "Expansión térmica"][:(n_plots)]):
        rows_s = sorted(rows, key=lambda r: r["node"])
        node_labels = [f"Nodo {r['node']}" for r in rows_s]
        ratios      = [r["ratio"] for r in rows_s]
        sl_vals     = [r["sl"]    for r in rows_s]
        sa_vals     = [r["sallow"] for r in rows_s]
 
        # Color by ratio
        colors = []
        for ratio in ratios:
            if ratio < 0.5:   colors.append("#3fb950")   # green  — OK
            elif ratio < 0.8: colors.append("#fbbf24")   # yellow — precaución
            else:             colors.append("#ff7b72")   # red    — crítico
 
        y_pos = range(len(rows_s))
        bars = ax.barh(list(y_pos), ratios, color=colors,
                       height=0.55, zorder=3, edgecolor=BG, linewidth=0.5)
 
        # Limit line at 1.0
        ax.axvline(1.0, color="#ff7b72", linewidth=1.5, linestyle="--",
                   alpha=0.7, zorder=4, label="Límite (S/Sa = 1.0)")
        # Limit line at 0.8
        ax.axvline(0.8, color="#fbbf24", linewidth=1, linestyle=":",
                   alpha=0.6, zorder=4)
 
        # Labels on bars
        for i, (bar, r, sl, sa) in enumerate(zip(bars, ratios, sl_vals, sa_vals)):
            ax.text(min(r + 0.02, 1.05), i,
                    f"  {r*100:.1f}%  ({sl:.0f}/{sa:.0f} psi)",
                    va='center', color=NODE_COL, fontsize=8,
                    fontfamily='monospace')
 
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(node_labels, color=TEXT if "TEXT" in dir() else NODE_COL,
                           fontsize=9, fontfamily='monospace')
        ax.set_xlim(0, max(max(ratios)*1.35 + 0.1, 1.15))
        ax.set_xlabel("S / Sallow  (utilización)", color=SUBTEXT,
                      fontsize=9, fontfamily='monospace')
        ax.set_title(title, color=NODE_COL, fontsize=10,
                     fontfamily='monospace', pad=8)
        ax.set_facecolor(BG)
        ax.tick_params(colors=SUBTEXT, labelsize=8)
        for sp in ax.spines.values(): sp.set_edgecolor(BORDER)
        ax.grid(True, axis='x', color=GRID_COL, linewidth=0.7, alpha=0.8, zorder=0)
        ax.set_axisbelow(True)
        ax.legend(fontsize=8, facecolor=PANEL2, edgecolor=BORDER,
                  labelcolor=NODE_COL, loc='lower right')
 
    fig.tight_layout(pad=2)
    return fig
 
 
def build_stress_dataframe(stress_rows):
    if not stress_rows: return pd.DataFrame()
    rows = []
    for r in sorted(stress_rows, key=lambda x: (x["lc"], x["node"])):
        stype_label = "Sostenida" if r["stype"] == "sus" else "Expansión"
        pct = r["ratio"] * 100
        rows.append({
            "Nodo":       r["node"],
            "Caso":       stype_label,
            "S (psi)":    round(r["sl"],    1),
            "Sallow (psi)": round(r["sallow"],1),
            "S/Sa  (%)":  round(pct, 1),
            "Slp (psi)":  round(r["slp"],   1),
            "Slb (psi)":  round(r["slb"],   1),
            "Shoop (psi)": round(r["shoop"], 1),
        })
    return pd.DataFrame(rows)
 
 
def color_stress_row(row):
    ratio = row["S/Sa  (%)"] / 100
    if ratio < 0.5:   bg = "#3fb95022"
    elif ratio < 0.8: bg = "#fbbf2422"
    else:             bg = "#ff7b7244"
    return [f"background-color:{bg}"] * len(row)
 
 
def make_figure(nodes, anchors, movements, scale, orientation):
    fig, ax = plt.subplots(figsize=(10,6))
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
 
    is_planta = "planta" in orientation
    for key, color, ls, lbl in [
        ("Peso",    DEFORM_W, "--",  "Deformada — Peso propio"),
        ("Térmica", DEFORM_T, "-.",  "Deformada — Expansión térmica"),
    ]:
        if not any(key in movements.get(n,{}) for n in nids): continue
        if is_planta and key == "Peso": continue
        xsd,ysd=[],[]
        for n,x0,y0 in zip(nids,xs0,ys0):
            ddx,ddy = _disp_xy(n,key,movements,orientation)
            xsd.append(x0+ddx*scale); ysd.append(y0+ddy*scale)
        ax.plot(xsd,ysd,color=color,linewidth=2.5,linestyle=ls,
                solid_capstyle='round',solid_joinstyle='round',
                label=f"{lbl}  (×{scale})",zorder=4)
        for x,y in zip(xsd,ysd):
            ax.plot(x,y,'o',color=color,markersize=5,
                    markeredgecolor=BG,markeredgewidth=1,zorder=6)
        _annotate_max(ax,nids,nodes,movements,key,color,scale,orientation)
 
    _draw_gravity_arrow(ax, orientation)
 
    is_vert = "Vertical" in orientation
    ax.set_xlabel("X lateral  (ft)" if is_vert else "X  (ft)",
                  color=SUBTEXT,fontsize=10,fontfamily='monospace')
    ax.set_ylabel("Y  (ft)" + ("  — Vista de planta" if is_planta else ""),
                  color=SUBTEXT,fontsize=10,fontfamily='monospace')
    ax.set_aspect('equal','datalim'); ax.margins(0.28)
    ax.tick_params(colors=SUBTEXT,labelsize=9)
    for sp in ax.spines.values(): sp.set_edgecolor(BORDER)
    ax.grid(True,color=GRID_COL,linewidth=0.8,alpha=0.9,zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc='best',fontsize=9,facecolor=PANEL2,
              edgecolor=BORDER,labelcolor=NODE_COL,framealpha=0.92)
    if is_planta:
        ax.text(0.99,0.02,
                "⊗  Gravedad perpendicular al plano (-Z)\n"
                "   Deflexión por peso fuera del plano — no mostrada",
                transform=ax.transAxes,ha='right',va='bottom',
                color=GRAV_COL,fontsize=8,fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.4',facecolor=BG,
                          edgecolor=GRAV_COL,alpha=0.85))
    fig.tight_layout()
    return fig
 
def _draw_anchor(ax,x,y):
    s=0.22
    ax.add_patch(plt.Polygon([[x,y],[x-s,y-s*1.2],[x+s,y-s*1.2]],
                              color=ANCHOR_COL,zorder=7,alpha=0.85))
    ax.plot([x-s*1.3,x+s*1.3],[y-s*1.2,y-s*1.2],
            color=ANCHOR_COL,linewidth=2.5,zorder=7)
    for i in range(5):
        ox=-s*1.2+i*(s*0.6)
        ax.plot([x+ox,x+ox-s*0.4],[y-s*1.2,y-s*1.7],
                color=ANCHOR_COL,linewidth=1,alpha=0.5,zorder=7)
 
def _draw_gravity_arrow(ax, orientation):
    if "planta" in orientation:
        ax.text(0.04,0.97,"⊗  g",transform=ax.transAxes,ha='left',va='top',
                color=GRAV_COL,fontsize=12,fontweight='bold',
                fontfamily='monospace',zorder=10)
    else:
        ax.annotate("",xy=(0.04,0.82),xytext=(0.04,0.97),
                    xycoords='axes fraction',textcoords='axes fraction',
                    arrowprops=dict(arrowstyle='->',color=GRAV_COL,lw=2.5),zorder=10)
        ax.text(0.06,0.895,"g",transform=ax.transAxes,ha='left',va='center',
                color=GRAV_COL,fontsize=11,fontweight='bold',
                fontfamily='monospace',zorder=10)
 
def _annotate_max(ax,nids,nodes,movements,key,color,scale,orientation):
    best,best_n=0,None
    for n in nids:
        ddx,ddy=_disp_xy(n,key,movements,orientation)
        mag=(ddx**2+ddy**2)**0.5
        if mag>best: best,best_n=mag,n
    if best_n is None or best<1e-6: return
    dx,dy,dz=movements[best_n][key]
    real_mag=(dx**2+dy**2+dz**2)**0.5
    ddx,ddy=_disp_xy(best_n,key,movements,orientation)
    ox=nodes[best_n][0]/12+ddx*scale
    oy=nodes[best_n][1]/12+ddy*scale
    ax.annotate(f"  Δmax={real_mag:.3f}\"",(ox,oy),color=color,
                fontsize=9,fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.3',facecolor=BG,
                          edgecolor=color,alpha=0.9),zorder=8)
 
def build_dataframe(nodes, movements, orientation):
    is_planta = "planta" in orientation
    rows=[]
    for n in sorted(nodes.keys()):
        for key in ["Peso","Térmica"]:
            if n not in movements or key not in movements[n]: continue
            dx,dy,dz=movements[n][key]
            mag=(dx**2+dy**2+dz**2)**0.5
            nota=""
            if is_planta and key=="Peso": nota="⊗ fuera del plano (-Z)"
            rows.append({"Nodo":n,"Carga":key,
                         "DX (in)":round(dx,4),"DY (in)":round(dy,4),
                         "DZ (in)":round(dz,4),"|D| (in)":round(mag,4),"Nota":nota})
    return pd.DataFrame(rows)
 
# ══════════════════════════════════════════════════════════
# STREAMLIT APP
# ══════════════════════════════════════════════════════════
 
st.set_page_config(page_title="PSI Simulator",page_icon="🔧",
                   layout="wide",initial_sidebar_state="expanded")
 
st.markdown("""<style>
[data-testid="stSidebar"]{background-color:#1e2530;border-right:2px solid #3a7bd5;}
[data-testid="stSidebar"] *{color:#f0f4ff !important;}
[data-testid="stSidebar"] .stMarkdown h3,[data-testid="stSidebar"] .stMarkdown h2{
  color:#7dd3fc !important;font-size:0.85rem;letter-spacing:.08em;
  text-transform:uppercase;margin-top:1.1rem;margin-bottom:.2rem;}
[data-testid="stSidebar"] hr{border-color:#3a4a6b !important;}
[data-testid="stSidebar"] .stSelectbox>div>div,
[data-testid="stSidebar"] .stNumberInput input{
  background-color:#2a3347 !important;color:#f0f4ff !important;
  border:1px solid #4a6090 !important;border-radius:6px;}
[data-testid="stSidebar"] label{color:#c8d8f0 !important;font-weight:500;}
[data-testid="stSidebar"] .stCheckbox label{color:#f0f4ff !important;}
[data-testid="stSidebar"] .stCaption{color:#7dd3fc !important;}
[data-testid="stSidebar"] .stTextInput input,[data-testid="stSidebar"] .stNumberInput input{
  background-color:#2a3347 !important;color:#f0f4ff !important;}
[data-testid="stExpander"]{background:#2a3347 !important;border:1px solid #4a6090;}
h1{color:#1e3a8a;font-family:monospace;font-size:1.8rem;}
h2,h3{color:#1d4ed8;font-family:monospace;}
.stButton>button{background-color:#2563eb;color:#fff;font-weight:bold;
  font-family:monospace;border:none;border-radius:8px;
  padding:.7rem 2rem;font-size:1rem;width:100%;letter-spacing:.05em;}
.stButton>button:hover{background-color:#1d4ed8;color:#fff;}
[data-testid="stMetric"]{background-color:#f0f7ff;border:1px solid #bfdbfe;
  border-radius:8px;padding:.5rem .8rem;}
</style>""", unsafe_allow_html=True)
 
# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🔧 PSI Simulator")
    st.markdown("*Pipe Stress Infinity*")
    st.divider()
 
    st.markdown("### ⚙️ Tipo de sistema")
    config = st.selectbox("Configuración",CONFIGS,index=0,label_visibility="collapsed")
 
    st.markdown("### 🧭 Orientación")
    orientation = st.selectbox("Orientación",ORIENTATIONS,index=0,label_visibility="collapsed")
    if "Vertical" in orientation:
        st.caption("↑ Caño principal sube en Y · Gravedad axial al tramo vertical")
    elif "planta" in orientation:
        st.caption("⊗ Vista de planta · Gravedad perpendicular al plano")
    else:
        st.caption("→ Caño corre en X · Gravedad deflecta hacia abajo")
 
    st.markdown("### 🔩 Tubería")
    c1,c2 = st.columns(2)
    with c1: size  = st.selectbox("NPS (in)",PIPE_SIZES,index=3)
    with c2: sched = st.selectbox("Sched.",SCHEDULES,index=2)
 
    # ── Material ──────────────────────────────────────────
    st.markdown("### 🧪 Material")
    mat_idx = st.selectbox("Material",MAT_NAMES,index=0,label_visibility="collapsed")
    mat_row = PRESET_MATERIALS[MAT_NAMES.index(mat_idx)]
    mat_id  = mat_row[1]
    is_custom = (mat_id == "CUSTOM")
 
    # Mostrar propiedades del material seleccionado (editable si es custom)
    with st.expander("⚙️ Propiedades del material", expanded=is_custom):
        if is_custom:
            st.caption("Ingresá las propiedades de tu material:")
            c3,c4 = st.columns(2)
            with c3:
                c_E   = st.number_input("E  (ksi)",    value=29000, step=500,
                                        help="Módulo de Young a temperatura ambiente")
                c_alp = st.number_input("α  (×10⁻⁶/°F)", value=6.07, step=0.1, format="%.2f",
                                        help="Coeficiente de expansión térmica")
            with c4:
                c_rho = st.number_input("ρ  (lb/in³)", value=0.283, step=0.001, format="%.3f",
                                        help="Densidad del material")
                c_nu  = st.number_input("ν  (adim.)",  value=0.30,  step=0.01, format="%.2f",
                                        help="Relación de Poisson")
            c_sh = st.number_input("Sh (psi) — Tensión admisible", value=15000, step=500,
                                   help="Tensión admisible a temperatura de operación (B31.1)")
            custom_mat = {
                "rho": c_rho,
                "nu":  c_nu,
                "alp": c_alp * 1e-6,
                "E":   c_E   * 1000,
                "sh":  c_sh,
            }
        else:
            # Solo lectura: mostrar propiedades del preset
            _, _, rho, nu, alp, E, sh = mat_row
            st.caption(f"ρ = {rho} lb/in³ &nbsp;|&nbsp; ν = {nu}")
            st.caption(f"α = {alp*1e6:.2f} ×10⁻⁶/°F &nbsp;|&nbsp; E = {E/1e6:.1f} Mpsi")
            st.caption(f"Sh = {sh:,} psi")
            custom_mat = None
 
    st.markdown("### 📐 Geometría (pies)")
    L1 = st.number_input("Longitud L1",min_value=1.0,max_value=200.0,value=10.0,step=0.5)
    needs_L2 = config not in ("Voladizo (1 apoyo empotrado)","Simplemente apoyado (2 apoyos)")
    needs_L3 = config in ("Forma U (lazo de expansión)","Forma Z (offset)")
    L2 = st.number_input("Longitud L2",min_value=1.0,max_value=200.0,value=8.0, step=0.5,disabled=not needs_L2)
    L3 = st.number_input("Longitud L3",min_value=1.0,max_value=200.0,value=10.0,step=0.5,disabled=not needs_L3)
 
    st.markdown("### 📦 Cargas")
    use_weight   = st.checkbox("Peso propio (gravedad)",value=True)
    use_pressure = st.checkbox("Presión interna",       value=False)
    use_thermal  = st.checkbox("Expansión térmica",     value=True)
    if use_pressure:
        pressure = st.number_input("Presión (psi)",min_value=0,max_value=10000,value=250,step=25)
    else:
        pressure = 0
    if use_thermal:
        c5,c6 = st.columns(2)
        with c5: T_op  = st.number_input("T op. (°F)",  value=400,step=10)
        with c6: T_ins = st.number_input("T inst. (°F)",value=70, step=5)
    else:
        T_op,T_ins=400,70
 
    st.markdown("### 🔍 Visualización")
    scale = st.slider("Ampliación deformada",min_value=1,max_value=500,value=50,step=5)
 
    st.divider()
    run_btn = st.button("▶  ANALIZAR",use_container_width=True)
 
# ── Panel principal ───────────────────────────────────────
st.markdown("# Pipe Stress Infinity — Simulador Visual")
orient_short = orientation.split("—")[0].strip()
mat_short    = mat_idx.split("—")[0].strip()
st.markdown(
    f"**Config.:** {config} &nbsp;|&nbsp; "
    f"**NPS {size}\" Sch.{sched}** &nbsp;|&nbsp; "
    f"**Material:** {mat_short} &nbsp;|&nbsp; "
    f"**Orientación:** {orient_short}")
st.divider()
 
if not run_btn:
    st.info("👈  Configurá los parámetros en el panel izquierdo y presioná **▶ ANALIZAR**.")
    st.stop()
if not use_weight and not use_thermal and not use_pressure:
    st.error("Seleccioná al menos una carga."); st.stop()
 
cfg = {
    "config":      config,   "orientation": orientation,
    "size":        size,     "sched":       sched,
    "mat_id":      mat_id,   "custom_mat":  custom_mat if is_custom else None,
    "L1_in":       L1*12,    "L2_in":       L2*12,   "L3_in":  L3*12,
    "use_weight":  use_weight,"use_thermal": use_thermal,"use_pressure": use_pressure,"pressure": pressure,
    "T_op":        T_op,      "T_ins":       T_ins,
    "scale":       scale,
}
 
with st.spinner("⏳ Ejecutando análisis PSI..."):
    try:
        script,nodes,anchors = build_psi_script(cfg)
        stdout,stderr,rc     = run_psi(script)
    except Exception as e:
        st.error(f"Error: {e}"); st.stop()
 
if rc!=0 or ("TRANSLATIONS" not in stdout and "MOVEMENTS" not in stdout):
    st.error("PSI no completó el análisis.")
    with st.expander("Ver log de error",expanded=True):
        st.code(stderr[-2000:]+"\n\n--- STDOUT ---\n"+stdout,language="text")
    st.stop()
 
movements = parse_movements(stdout, use_weight, use_thermal)
if not movements:
    st.error("No se obtuvieron desplazamientos."); st.stop()
 
# ── Métricas ─────────────────────────────────────────────
st.markdown("### 📊 Resultados")
is_planta = "planta" in orientation
cols_m = st.columns(4)
for key,lbl,col in [("Peso","🟠 Peso propio",cols_m[0]),("Térmica","🔴 Expansión térmica",cols_m[1])]:
    vals=[(dx**2+dy**2+dz**2)**0.5 for nd in movements.values() if key in nd for dx,dy,dz in [nd[key]]]
    if vals:
        nota="Δ máx. (fuera del plano)" if (is_planta and key=="Peso") else "Δ máximo"
        col.metric(lbl,f"{max(vals):.4f} \"",nota)
max_all=max((dx**2+dy**2+dz**2)**0.5 for nd in movements.values() for dx,dy,dz in nd.values())
cols_m[2].metric("🔵 Δ total máximo",f"{max_all:.4f} \"","todas las cargas")
cols_m[3].metric("📍 Nodos",len(nodes))
st.divider()
 
# ── Gráfico ──────────────────────────────────────────────
st.markdown("### 🖼️ Visualización")
fig = make_figure(nodes,anchors,movements,scale,orientation)
st.pyplot(fig,use_container_width=True)
plt.close(fig)
 
# ── Tabla ────────────────────────────────────────────────
st.markdown("### 📋 Tabla de desplazamientos  (pulgadas)")
df = build_dataframe(nodes,movements,orientation)
def color_row(row):
    c="#f0883e22" if row["Carga"]=="Peso" else "#ff7b7222"
    return [f"background-color:{c}"]*len(row)
fmt={"DX (in)":"{:+.4f}","DY (in)":"{:+.4f}","DZ (in)":"{:+.4f}","|D| (in)":"{:.4f}"}
st.dataframe(df.style.apply(color_row,axis=1).format(fmt),
             use_container_width=True,hide_index=True)
 
# ── Tensiones ─────────────────────────────────────────────────────
st.divider()
st.markdown("### ⚡ Tensiones según B31.1")
 
stress_rows = parse_stresses(stdout)
if stress_rows:
    # Semáforo de tensiones
    max_ratio = max(r["ratio"] for r in stress_rows)
    if max_ratio < 0.5:
        st.success(f"✅ Sistema OK — Utilización máxima: {max_ratio*100:.1f}%  (< 50%)")
    elif max_ratio < 1.0:
        st.warning(f"⚠️ Verificar — Utilización máxima: {max_ratio*100:.1f}%")
    else:
        st.error(f"🚨 EXCEDE ADMISIBLE — Utilización máxima: {max_ratio*100:.1f}%")
 
    col_s1, col_s2 = st.columns([1.2, 2])
    with col_s1:
        # Tabla de tensiones
        df_s = build_stress_dataframe(stress_rows)
        st.markdown("**Tabla de tensiones**")
        st.dataframe(
            df_s.style.apply(color_stress_row, axis=1).format({
                "S (psi)":"{:.1f}","Sallow (psi)":"{:.1f}",
                "S/Sa  (%)":"{:.1f}","Slp (psi)":"{:.1f}",
                "Slb (psi)":"{:.1f}","Shoop (psi)":"{:.1f}"}),
            use_container_width=True, hide_index=True)
        st.caption("🟢 < 50%  🟡 50–80%  🔴 > 80%  &nbsp;|&nbsp; Sl = tensión total longitudinal · Slp = presión · Slb = flexión · Shoop = circunferencial")
    with col_s2:
        fig_s = make_stress_figure(stress_rows, nodes)
        if fig_s:
            st.pyplot(fig_s, use_container_width=True)
            plt.close(fig_s)
else:
    st.info("Sin datos de tensión disponibles.")
 
with st.expander("📄 Ver log de PSI"):
    st.code(stdout,language="text")
