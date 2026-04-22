#!/bin/bash
# ╔══════════════════════════════════════════════╗
# ║  PSI Simulator — Script de instalación      ║
# ╚══════════════════════════════════════════════╝
set -e
echo ""
echo "═══════════════════════════════════════════════"
echo "  PSI Visual Simulator — Instalación"
echo "═══════════════════════════════════════════════"
echo ""

# 1. Dependencias Python
echo "[1/3] Instalando dependencias Python..."
pip install matplotlib git+https://github.com/denisgomes/psi.git

# 2. Parche numpy (bug en PSI 0.0.1 con NumPy moderno)
echo ""
echo "[2/3] Aplicando parche de compatibilidad NumPy..."
PSI_LOADS=$(python3 -c "import psi, os; print(os.path.join(os.path.dirname(psi.__file__), 'loads.py'))")
python3 - "$PSI_LOADS" << 'PYEOF'
import sys
path = sys.argv[1]
with open(path, 'r') as f:
    content = f.read()
fixed = content.replace('wxl, wyl, wzl = wl\n', 'wxl, wyl, wzl = wl[:, 0]\n')
count = content.count('wxl, wyl, wzl = wl\n')
with open(path, 'w') as f:
    f.write(fixed)
print(f"   → {count} ocurrencia(s) parcheadas en {path}")
PYEOF

echo ""
echo "[3/3] Verificando instalación..."
python3 -c "import psi; import matplotlib; print('   → OK')"

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✔  Instalación completada."
echo ""
echo "  Para ejecutar el simulador:"
echo "     python3 app.py"
echo "═══════════════════════════════════════════════"
echo ""
