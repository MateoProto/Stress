# PSI Visual Simulator
## Simulador visual de esfuerzos en cañerías con Pipe Stress Infinity

---

### ¿Qué hace?

Simula visualmente configuraciones básicas de sistemas de cañerías y calcula deformaciones usando la librería **PSI (Pipe Stress Infinity)**. Muestra en pantalla:

- La geometría original de la cañería
- La forma deformada por **peso propio** (naranja)
- La forma deformada por **expansión térmica** (rojo)
- Tabla de desplazamientos DX, DY, DZ en cada nodo

### Configuraciones disponibles

| Tipo | Descripción |
|------|-------------|
| Voladizo | 1 apoyo empotrado, extremo libre |
| Simplemente apoyado | Apoyos en ambos extremos |
| Forma L | Dos tramos perpendiculares |
| Forma U | Lazo de expansión |
| Forma Z | Offset con dos tramos paralelos |

### Instalación (primera vez)

```bash
bash instalar.sh
```

Esto instala matplotlib y PSI, y aplica un parche de compatibilidad con NumPy moderno.

### Ejecución

```bash
python3 app.py
```

Requiere Python 3.8+ con `tkinter` instalado.

> **Linux:** si tkinter no está instalado:  
> `sudo apt install python3-tk`

### Parámetros configurables

- **Diámetro nominal** y **Schedule** de la tubería (estándar ASME)
- **Material:** A53A Gr.A (B31.1) — único disponible en PSI community
- **Longitudes** de cada tramo (en pies)
- **Temperatura de operación** e **instalación** (°F)
- **Factor de ampliación** de la deformada (para visualización)

### Unidades

| Magnitud | Unidad PSI |
|----------|-----------|
| Longitud | pulgadas (entrada en pies, conversión automática) |
| Desplazamiento | pulgadas |
| Temperatura | °F |
| Presión | psi |

---

*Basado en PSI 0.0.1 — Denis Gomes (GPLv3)*
