"""
╔══════════════════════════════════════════════════════╗
║  Pipe Stress Infinity — Simulador Visual             ║
║  Análisis de esfuerzos y deformaciones en cañerías   ║
╚══════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess, tempfile, os, re, sys

BG        = "#0d1117"
PANEL     = "#161b22"
PANEL2    = "#1c2128"
ACCENT    = "#58a6ff"
ACCENT2   = "#3fb950"
WARN      = "#f78166"
TEXT      = "#e6edf3"
SUBTEXT   = "#7d8590"
BORDER    = "#30363d"
ENTRY_BG  = "#21262d"

PIPE_COL   = "#58a6ff"
DEFORM_W   = "#f0883e"
DEFORM_T   = "#ff7b72"
ANCHOR_COL = "#3fb950"
NODE_COL   = "#e6edf3"
GRID_COL   = "#21262d"

PIPE_SIZES = ["2", "3", "4", "6", "8", "10", "12", "16"]
SCHEDULES  = ["10", "20", "40", "80", "160"]
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
    footer = f"b311=B31167('B31.1')\nb311.apply([{elems_str}])\nmdl.analyze()\ndisp=Movements('r1',[{','.join(lc_names)}])\ndisp.to_screen()\n"
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
        in_tbl = False
        cur_n  = None
        for line in lines:
            if "TRANSLATIONS" in line and "ROTATIONS" in line:
                in_tbl = True; continue
            if not in_tbl: continue
            m = re.match(r"\s*(\d+)\s+(l\d+)\s*\(\s*(\w+)\s*\)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m:
                cur_n = int(m.group(1))
                key = "peso" if m.group(3).lower()=="sus" else "térmica"
                results.setdefault(cur_n,{})[key] = (float(m.group(4)),float(m.group(5)),float(m.group(6)))
                continue
            m2 = re.match(r"\s+(l\d+)\s*\(\s*(\w+)\s*\)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m2 and cur_n is not None:
                key = "peso" if m2.group(2).lower()=="sus" else "térmica"
                results.setdefault(cur_n,{})[key] = (float(m2.group(3)),float(m2.group(4)),float(m2.group(5)))
    else:
        single_key = "peso" if use_weight else "térmica"
        in_tbl = False
        for line in lines:
            if re.match(r"\s*NODE\s+DX\s+DY", line):
                in_tbl = True; continue
            if not in_tbl: continue
            m = re.match(r"\s*(\d+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m:
                results.setdefault(int(m.group(1)),{})[single_key] = (float(m.group(2)),float(m.group(3)),float(m.group(4)))
    return results

def plot_system(ax, nodes, anchors, movements, scale):
    ax.clear()
    ax.set_facecolor(BG)
    nids = sorted(nodes.keys())
    xs0  = [nodes[n][0]/12 for n in nids]
    ys0  = [nodes[n][1]/12 for n in nids]

    # Original
    ax.plot(xs0, ys0, color=PIPE_COL, linewidth=5,
            solid_capstyle='round', solid_joinstyle='round',
            zorder=3, label="Geometría original")
    for n,x,y in zip(nids,xs0,ys0):
        ax.plot(x,y,'o',color=NODE_COL,markersize=7,
                markeredgecolor=BG,markeredgewidth=1.2,zorder=5)
        ax.annotate(f" {n}",(x,y),color=SUBTEXT,fontsize=8,
                    va='center',fontfamily='monospace',zorder=6)
    for n in anchors:
        _draw_anchor(ax, nodes[n][0]/12, nodes[n][1]/12)

    # Deformadas
    for key, color, ls, lbl in [
        ("peso",    DEFORM_W, "--",  "Deformada — Peso propio"),
        ("térmica", DEFORM_T, "-.",  "Deformada — Expansión térmica"),
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
        _annotate_max(ax,nids,nodes,movements,key,color,scale)

    ax.set_aspect('equal','datalim')
    ax.margins(0.25)
    ax.set_xlabel("X  (ft)",color=SUBTEXT,fontsize=9,fontfamily='monospace')
    ax.set_ylabel("Y  (ft)",color=SUBTEXT,fontsize=9,fontfamily='monospace')
    ax.tick_params(colors=SUBTEXT,labelsize=8)
    for sp in ax.spines.values(): sp.set_edgecolor(BORDER)
    ax.grid(True,color=GRID_COL,linewidth=0.8,alpha=0.9,zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc='best',fontsize=8,facecolor=PANEL2,
              edgecolor=BORDER,labelcolor=TEXT,framealpha=0.92)

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

def _annotate_max(ax,nids,nodes,movements,key,color,scale):
    best_mag,best_n=0,None
    for n in nids:
        if n in movements and key in movements[n]:
            dx,dy,dz=movements[n][key]
            mag=(dx**2+dy**2+dz**2)**0.5
            if mag>best_mag: best_mag,best_n=mag,n
    if best_n is None or best_mag<0.001: return
    dx,dy,_=movements[best_n][key]
    ox=nodes[best_n][0]/12+dx*scale/12
    oy=nodes[best_n][1]/12+dy*scale/12
    ax.annotate(f"  Δmax={best_mag:.3f}\"",(ox,oy),color=color,
                fontsize=8,fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.25',facecolor=BG,
                          edgecolor=color,alpha=0.85),zorder=8)

def populate_table(tree, nodes, movements):
    for r in tree.get_children(): tree.delete(r)
    for n in sorted(nodes.keys()):
        for key in ["peso","térmica"]:
            if n not in movements or key not in movements[n]: continue
            dx,dy,dz=movements[n][key]
            mag=(dx**2+dy**2+dz**2)**0.5
            tree.insert("",tk.END,
                        values=(n,key.capitalize(),
                                f"{dx:+.4f}",f"{dy:+.4f}",f"{dz:+.4f}",f"{mag:.4f}"),
                        tags=(key,))
    tree.tag_configure("peso",    background=ENTRY_BG,foreground=DEFORM_W)
    tree.tag_configure("térmica", background=ENTRY_BG,foreground=DEFORM_T)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pipe Stress Infinity — Simulador Visual")
        self.configure(bg=BG)
        self.geometry("1340x840")
        self.minsize(1100,700)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        self.columnconfigure(0,weight=0)
        self.columnconfigure(1,weight=1)
        self.rowconfigure(0,weight=1)
        left=tk.Frame(self,bg=PANEL,width=326)
        left.grid(row=0,column=0,sticky="nsew")
        left.grid_propagate(False)
        left.columnconfigure(0,weight=1)
        self._build_left(left)
        right=tk.Frame(self,bg=BG)
        right.grid(row=0,column=1,sticky="nsew")
        right.rowconfigure(0,weight=3)
        right.rowconfigure(1,weight=1)
        right.columnconfigure(0,weight=1)
        self._build_right(right)

    def _build_left(self,p):
        tk.Frame(p,bg=ACCENT,height=3).pack(fill=tk.X)
        hdr=tk.Frame(p,bg=PANEL); hdr.pack(fill=tk.X,padx=18,pady=(16,6))
        tk.Label(hdr,text="PSI  Simulator",bg=PANEL,fg=ACCENT,
                 font=("Courier New",15,"bold")).pack(anchor="w")
        tk.Label(hdr,text="Pipe Stress Infinity",bg=PANEL,fg=SUBTEXT,
                 font=("Courier New",8)).pack(anchor="w")
        tk.Frame(p,bg=BORDER,height=1).pack(fill=tk.X,padx=18,pady=(8,0))

        cv=tk.Canvas(p,bg=PANEL,highlightthickness=0,bd=0)
        sb=ttk.Scrollbar(p,orient="vertical",command=cv.yview)
        self._sf=tk.Frame(cv,bg=PANEL)
        self._sf.bind("<Configure>",lambda e:cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0),window=self._sf,anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left",fill="both",expand=True)
        sb.pack(side="right",fill="y")
        cv.bind_all("<MouseWheel>",lambda e:cv.yview_scroll(-1*(e.delta//120),"units"))

        f=self._sf; f.columnconfigure(0,weight=1)

        self._sec(f,"TIPO DE SISTEMA")
        self.var_cfg=self._combo(f,"Configuración:",CONFIGS,CONFIGS[0])
        self.var_cfg.trace_add("write",self._on_cfg)

        self._sec(f,"PROPIEDADES DE TUBERÍA")
        self.var_size=self._combo(f,"Diámetro nominal (NPS, in):",PIPE_SIZES,"6")
        self.var_sched=self._combo(f,"Schedule:",SCHEDULES,"40")
        tk.Label(f,text="  Material: A53A Gr.A  (B31.1)",
                 bg=PANEL,fg=SUBTEXT,font=("Courier New",8)).pack(anchor="w",padx=18,pady=(2,0))

        self._sec(f,"GEOMETRÍA")
        self.var_L1=self._entry(f,"Longitud L1 (ft):","10.0")
        self.lbl_L2,self.var_L2=self._entry_lbl(f,"Longitud L2 (ft):","8.0")
        self.lbl_L3,self.var_L3=self._entry_lbl(f,"Longitud L3 (ft):","10.0")

        self._sec(f,"CARGAS")
        self.var_use_w=self._check(f,"✔  Peso propio (gravedad)")
        self.var_use_t=self._check(f,"✔  Expansión térmica")
        self.var_Top=self._entry(f,"Temperatura de operación (°F):","400")
        self.var_Tins=self._entry(f,"Temperatura de instalación (°F):","70")

        self._sec(f,"VISUALIZACIÓN")
        self.var_scale=self._entry(f,"Factor de ampliación de deformada:","50")

        tk.Frame(f,bg=BORDER,height=1).pack(fill=tk.X,padx=18,pady=(14,8))
        self._btn=tk.Button(f,text="▶   ANALIZAR",
                            bg=ACCENT,fg=BG,
                            font=("Courier New",11,"bold"),
                            relief=tk.FLAT,cursor="hand2",
                            activebackground="#388bfd",activeforeground=BG,
                            command=self._run,pady=10)
        self._btn.pack(fill=tk.X,padx=18,pady=(0,6))

        self.var_st=tk.StringVar(value="Listo para analizar.")
        tk.Label(f,textvariable=self.var_st,bg=PANEL,fg=SUBTEXT,
                 font=("Courier New",8),wraplength=270,justify="left"
                 ).pack(padx=18,pady=(0,20),anchor="w")

        self._on_cfg()

    def _build_right(self,p):
        fw=tk.Frame(p,bg=BG)
        fw.grid(row=0,column=0,sticky="nsew",padx=10,pady=10)
        self.fig,self.ax=plt.subplots(figsize=(10,6))
        self.fig.patch.set_facecolor(BG)
        self.ax.set_facecolor(BG)
        self._placeholder()
        self.canvas=FigureCanvasTkAgg(self.fig,master=fw)
        self.canvas.get_tk_widget().configure(bg=BG,highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH,expand=True)

        tw=tk.Frame(p,bg=PANEL2)
        tw.grid(row=1,column=0,sticky="nsew",padx=10,pady=(0,10))
        tw.columnconfigure(0,weight=1)
        tk.Label(tw,text="DESPLAZAMIENTOS NODALES  (pulgadas)",
                 bg=PANEL2,fg=ACCENT,
                 font=("Courier New",9,"bold")).pack(anchor="w",padx=12,pady=(8,2))
        cols=("Nodo","Carga","DX","DY","DZ","|D| total")
        self.tree=ttk.Treeview(tw,columns=cols,show="headings",
                                style="PSI.Treeview",height=5)
        for c,w in zip(cols,[60,90,90,90,90,100]):
            self.tree.heading(c,text=c)
            self.tree.column(c,width=w,anchor="center",minwidth=w)
        self.tree.pack(fill=tk.BOTH,expand=True,padx=12,pady=(0,10))

    def _placeholder(self):
        self.ax.clear()
        self.ax.set_facecolor(BG)
        self.ax.set_xticks([]); self.ax.set_yticks([])
        for sp in self.ax.spines.values(): sp.set_edgecolor(BORDER)
        self.ax.text(0.5,0.55,
                     "Configure los parámetros\ny presione ▶ ANALIZAR",
                     transform=self.ax.transAxes,ha='center',va='center',
                     color=SUBTEXT,fontsize=13,fontfamily='monospace',linespacing=1.8)
        self.canvas.draw()

    def _sec(self,p,t):
        f=tk.Frame(p,bg=PANEL); f.pack(fill=tk.X,padx=18,pady=(14,3))
        tk.Label(f,text=t,bg=PANEL,fg=ACCENT2,
                 font=("Courier New",8,"bold")).pack(anchor="w")
        tk.Frame(f,bg=ACCENT2,height=1).pack(fill=tk.X,pady=(2,0))

    def _combo(self,p,lbl,vals,default):
        tk.Label(p,text=lbl,bg=PANEL,fg=TEXT,
                 font=("Courier New",9)).pack(anchor="w",padx=18,pady=(6,0))
        var=tk.StringVar(value=default)
        ttk.Combobox(p,textvariable=var,values=vals,state="readonly",
                     font=("Courier New",9),style="PSI.TCombobox"
                     ).pack(fill=tk.X,padx=18,pady=(2,0),ipady=2)
        return var

    def _entry(self,p,lbl,default):
        tk.Label(p,text=lbl,bg=PANEL,fg=TEXT,
                 font=("Courier New",9)).pack(anchor="w",padx=18,pady=(6,0))
        var=tk.StringVar(value=default)
        tk.Entry(p,textvariable=var,bg=ENTRY_BG,fg=TEXT,
                 insertbackground=TEXT,relief=tk.FLAT,
                 font=("Courier New",9),
                 highlightthickness=1,highlightcolor=ACCENT,
                 highlightbackground=BORDER
                 ).pack(fill=tk.X,padx=18,pady=(2,0),ipady=4)
        return var

    def _entry_lbl(self,p,lbl,default):
        label=tk.Label(p,text=lbl,bg=PANEL,fg=TEXT,
                       font=("Courier New",9))
        label.pack(anchor="w",padx=18,pady=(6,0))
        var=tk.StringVar(value=default)
        tk.Entry(p,textvariable=var,bg=ENTRY_BG,fg=TEXT,
                 insertbackground=TEXT,relief=tk.FLAT,
                 font=("Courier New",9),
                 highlightthickness=1,highlightcolor=ACCENT,
                 highlightbackground=BORDER
                 ).pack(fill=tk.X,padx=18,pady=(2,0),ipady=4)
        return label,var

    def _check(self,p,lbl):
        var=tk.BooleanVar(value=True)
        tk.Checkbutton(p,text=lbl,variable=var,
                       bg=PANEL,fg=TEXT,selectcolor=ENTRY_BG,
                       activebackground=PANEL,activeforeground=ACCENT,
                       font=("Courier New",9)
                       ).pack(anchor="w",padx=18,pady=(6,0))
        return var

    def _on_cfg(self,*_):
        cfg=self.var_cfg.get()
        needs_L2 = cfg not in ("Voladizo (1 apoyo empotrado)","Simplemente apoyado (2 apoyos)")
        needs_L3 = cfg in ("Forma U (lazo de expansión)","Forma Z (offset)")
        self.lbl_L2.configure(fg=TEXT if needs_L2 else SUBTEXT)
        self.lbl_L3.configure(fg=TEXT if needs_L3 else SUBTEXT)

    def _run(self):
        self._btn.configure(state=tk.DISABLED,text="⏳  Analizando...")
        self.var_st.set("Ejecutando análisis PSI...")
        self.update()
        try:    self._do()
        finally:self._btn.configure(state=tk.NORMAL,text="▶   ANALIZAR")

    def _do(self):
        try:    cfg=self._collect()
        except ValueError as e:
            messagebox.showerror("Error de entrada",str(e)); self.var_st.set("⚠ Error."); return
        if not cfg["use_weight"] and not cfg["use_thermal"]:
            messagebox.showwarning("Sin cargas","Seleccioná al menos una carga.")
            self.var_st.set("⚠ Sin cargas."); return
        try:
            script,nodes,anchors=build_psi_script(cfg)
            stdout,stderr=run_psi(script)
        except Exception as e:
            messagebox.showerror("Error",str(e)); self.var_st.set(f"⚠ {e}"); return
        if "Analysis complete" not in stdout:
            messagebox.showerror("PSI falló",(stderr+stdout)[-600:])
            self.var_st.set("⚠ Análisis fallido."); return
        movements=parse_movements(stdout,cfg["use_weight"],cfg["use_thermal"])
        if not movements:
            messagebox.showerror("Sin resultados","PSI no devolvió desplazamientos.")
            self.var_st.set("⚠ Sin resultados."); return
        plot_system(self.ax,nodes,anchors,movements,cfg["scale"])
        self.canvas.draw()
        populate_table(self.tree,nodes,movements)
        n=sum(len(v) for v in movements.values())
        self.var_st.set(f"✔ Completo — {len(nodes)} nodos, {n} casos. Ampliación ×{cfg['scale']}.")

    def _collect(self):
        def f(s,n):
            try:
                v=float(s.strip())
                if v<=0: raise ValueError()
                return v
            except: raise ValueError(f"'{n}' debe ser número positivo.")
        def fa(s,n):
            try: return float(s.strip())
            except: raise ValueError(f"'{n}' debe ser número.")
        return {
            "config":     self.var_cfg.get(),
            "size":       self.var_size.get(),
            "sched":      self.var_sched.get(),
            "L1_in":      f(self.var_L1.get(),"L1")*12,
            "L2_in":      f(self.var_L2.get(),"L2")*12,
            "L3_in":      f(self.var_L3.get(),"L3")*12,
            "use_weight": self.var_use_w.get(),
            "use_thermal":self.var_use_t.get(),
            "T_op":       fa(self.var_Top.get(),"T operación"),
            "T_ins":      fa(self.var_Tins.get(),"T instalación"),
            "scale":      int(f(self.var_scale.get(),"Escala")),
        }

    def _apply_styles(self):
        s=ttk.Style(self); s.theme_use("clam")
        s.configure("PSI.Treeview",background=ENTRY_BG,foreground=TEXT,
                    fieldbackground=ENTRY_BG,rowheight=24,
                    font=("Courier New",9),borderwidth=0)
        s.configure("PSI.Treeview.Heading",background=PANEL,foreground=ACCENT,
                    font=("Courier New",8,"bold"),borderwidth=0,relief=tk.FLAT)
        s.map("PSI.Treeview",
              background=[("selected","#2d333b")],foreground=[("selected",TEXT)])
        s.configure("PSI.TCombobox",fieldbackground=ENTRY_BG,background=ENTRY_BG,
                    foreground=TEXT,selectbackground=ENTRY_BG,selectforeground=TEXT,
                    bordercolor=BORDER,arrowcolor=ACCENT)
        s.map("PSI.TCombobox",
              fieldbackground=[("readonly",ENTRY_BG)],foreground=[("readonly",TEXT)],
              selectbackground=[("readonly",ENTRY_BG)])
        s.configure("Vertical.TScrollbar",background=PANEL,
                    troughcolor=PANEL,bordercolor=BORDER,arrowcolor=SUBTEXT)

if __name__=="__main__":
    try:
        subprocess.run(['psi','--version'],capture_output=True,timeout=5)
    except FileNotFoundError:
        print("ERROR: PSI no encontrado.\nInstalá: pip install git+https://github.com/denisgomes/psi.git")
        sys.exit(1)
    App().mainloop()
