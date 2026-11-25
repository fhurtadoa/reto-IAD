# Guía Docente — Carga, Personalización y Revisión de Ejercicios en OptiCompromise

**Curso:** Introducción al Análisis de Decisiones (IAD) · Facultad de Minas — Universidad Nacional de Colombia (Sede Medellín)  
**Plataforma:** OptiCompromise (Next.js 15 + FastAPI + SciPy HiGHS/SLSQP + openpyxl + SheetJS CE)

Esta guía práctica está pensada para **docentes y monitores** que desean preparar talleres, exámenes, variantes por estudiante o casos de clase y evaluarlos en **OptiCompromise** sin necesidad de programar.

---

## Alcance del motor (qué ejercicios admite y cuáles no)

- **Admitidos:** Modelos deterministas lineales y enteros mixtos (MIP) con **2 o más funciones objetivo lineales** (`maximize` o `minimize`), restricciones lineales (`<=`, `>=`, `==`) y variables continuas (`continuous`, ℝ), enteras (`integer`, ℤ) o binarias (`binary`, {0, 1}).
- **Visualizaciones disponibles según dimensión:**
  - Exactamente **2 objetivos**: habilita **Sensibilidad de pesos** (barrido de 21 puntos entre 0 y 1).
  - Exactamente **2 variables**: habilita **Región Factible** en el espacio de decisiones (incluyendo malla discreta si hay variables enteras/binarias) y proyección de **Zona Factible** en 2D.
  - **3 o más objetivos**: habilita **Espacio 3D** rotatorio y **Radar (% Logro)**.
- **No admitidos en el motor:** Expresiones no lineales con productos de variables (`x1 * x2`), potencias (`x1^2`), raíces, división por variables, simulación estocástica, árboles de decisión, redes neuronales o matrices de comparaciones pareadas AHP / matrices de alternativas finitas discretas.

---

## Carga de ejercicios desde la plantilla oficial

1. En **Formular**, pulsa **Obtener plantilla (.xlsx)**. [Plantilla oficial de OptiCompromise](../web/public/plantilla-ejercicio-iad.xlsx).
2. Diligencia **Modelo**. Usa **Guia_Docente** para consultar los campos y **Ejemplo_Papel** para ver un caso diligenciado.
3. Guarda el `.xlsx` (o exporta a `.csv` con `,` o `;`) y pulsa **Cargar ejercicio**. OptiCompromise lee exclusivamente la hoja **Modelo** (sin fórmulas sin valor calculado). Revisa el estado del motor y la formulación que se reconstruyó. También puedes usar **Guardar (.json)** en **Formular** para conservar una copia editable del modelo en formato JSON, o abrir los 6 casos precargados desde **Ejemplos** en el pie de página.

### Estructura exacta de columnas

Las primeras **5 columnas** son fijas, seguidas de **una columna por cada variable de decisión**:

`Seccion` | `Nombre` | `Tipo_o_Sentido` | `Min_o_RHS` | `Max_o_Peso` | `<var_1>` | `<var_2>` | `...`

### Estructura exacta de filas y valores válidos

| Valor en `Seccion` | `Nombre` | `Tipo_o_Sentido` | `Min_o_RHS` | `Max_o_Peso` | Columnas de variables (`<var_i>`) |
|---|---|---|---|---|---|
| **`Meta`** *(1 fila)* | Título del ejercicio | Enunciado, contexto y unidades | Semilla opcional para Pareto con ≥4 objetivos (ej. `42`) | Fuente o referencia académica | Vacías |
| **`Variable`** *(1 fila por variable)* | Identificador único (ej. `x1`, `x1_1 (M1 Prensa)`) | `continuous`, `integer` o `binary` *(acepta `continua`, `entera`, `binaria`)* | Cota inferior para continuas y enteras. Vacío = `0`. Usa `-inf` (o `-∞`) si no tiene cota inferior | Cota superior para continuas y enteras. Vacío = sin límite (`+inf` / `+∞`). Al cargar binarias, la aplicación usa `[0, 1]` | Vacías |
| **`Objetivo`** *(≥ 2 filas)* | Nombre del criterio y unidad | `maximize` o `minimize` *(acepta `max`, `min`, `maximizar`, `minimizar`)* | Vacío | Peso entre `0` y `1`. **O todos completos sumando `1.0` (±0.001) o todos vacíos** (asigna pesos iguales $1/q$) | Coeficiente numérico real de cada variable (vacío = `0`) |
| **`Restriccion`** *(0 o más filas)* | Nombre de la restricción | `<=` (`≤`), `>=` (`≥`), o `==` (`=`) | Valor numérico del lado derecho (RHS) | Vacío | Coeficiente numérico real de cada variable (vacío = `0`) |

> **Tip para igualdad en Excel:** Si escribes `=` solo en una celda, Excel intentará interpretarlo como fórmula. Escribe `==` (recomendado) o antepón un apóstrofe `'=` para conservarlo como texto.

### Cómo personalizar variantes por estudiante (Ejemplo: Taller 3 Producción de Papel con dígito `n`)

La hoja **Ejemplo_Papel** contiene los datos base del Taller 1 (3 máquinas × 4 tipos de papel, 2 objetivos y 7 restricciones).

1. Abre una copia de la plantilla y traslada a **Modelo** las filas y columnas de **Ejemplo_Papel** que usarás como punto de partida.
2. En la fila `Restriccion` llamada `Demanda mínima · Prensa`, cambia `Min_o_RHS` de `77` a `77 + n` (para `n = 6`, escribe **`83`**).
3. En las dos filas `Objetivo`, actualiza `Max_o_Peso`:
   - `Costo (millones de pesos)`: `0.5 + 0.01*n` → **`0.56`**
   - `Calidad (indicador × ton)`: `0.5 - 0.01*n` → **`0.44`**
4. Opcionalmente actualiza el título en `Meta` (ej. `Producción de papel · Variante n=6`). *Por privacidad, registra únicamente el dígito `n` y no el número completo de documento.*
5. Guarda el `.xlsx` y ábrelo con **Cargar ejercicio**.

### Qué NO hacer en hojas de cálculo (errores frecuentes)

1. **No uses nombres de columnas reservados como nombres de variables sin prefijo:** Evita llamar a una variable `Seccion`, `Sección`, `Nombre`, `Tipo_o_Sentido`, `Min_o_RHS`, `Max_o_Peso`, `Tipo`, `Elemento`, `Name`, `Variable`, `Description`, `Descripcion`, `Pareto_seed`, `Referencia`, `Fuente`, `Var_type`, `Tipo_var`, `Min`, `Max`, `Lower_bound`, `Upper_bound`, `Lb`, `Ub`, `Sense`, `Sentido`, `Peso`, `Weight`, `Operador`, `Rhs` o `Ld`. Si alguna variable debe llamarse así, su columna de coeficientes debe llevar el prefijo **`Coef: `** (ej. `Coef: Max`), tal como hace automáticamente OptiCompromise al exportar.
2. **No escribas expresiones no lineales o texto algebraico en celdas de coeficientes:** No escribas `x1*x2`, `50*x1` ni `1/53` como texto en Excel; escribe siempre el coeficiente numérico calculado (ej. `0.0188679245`).
3. **No mezcles pesos vacíos y pesos numéricos:** O diligencias `Max_o_Peso` en todos los objetivos (sumando `1.0`), o dejas la columna vacía en todos.
4. **No dejes filas `Restriccion` incompletas:** Si no hay restricciones, puedes omitir la fila `Restriccion`.
5. **No dupliques nombres de variables** ni pongas `Min_o_RHS > Max_o_Peso`.

---

## Formular con el editor `Modo Algebraico`

Ideal para dictar o copiar rápidamente un enunciado de tablero durante la clase:

1. En **Formular**, pulsa **Nuevo modelo** y asegúrate de estar en la pestaña **Modo Algebraico**.
2. Pega o escribe el modelo en texto lineal. Ejemplo listo para copiar (Caso Celdas):

```text
# Comentarios opcionales con # o //
Max Z1 (Utilidad Total USD) = 1000*x1 + 3000*x2
Min Z2 (Emision Contaminantes kg) = x1 + 2*x2
s.a.
x1 + x2 <= 400
1000*x1 + 3000*x2 >= 300000
```

3. **Reglas de sintaxis del parser algebraico:**
   - Objetivos: `Max Z1 (Nombre) = ...` o `Min Z2 = ...` (sin términos constantes independientes en objetivos).
   - Separador de restricciones: `s.a.`, `sujeto a:` o `restricciones:`.
   - Restricciones: soporta `<=`, `>=`, `=`, `==`, símbolos Unicode (`≤`, `≥`, `−`), coma decimal (`2,5`) y variables o constantes en ambos lados (ej. `x1 <= 2*x2 + 10`).
4. **Paso obligatorio:** Pulsa **Aplicar Ecuaciones y Resolver**.
   - Mientras existan ediciones en texto sin aplicar, la barra de navegación muestra la píldora **Borrador sin aplicar** y valida las ecuaciones al cambiar a **Ver método** o **Explorar resultados**. Si encuentra errores, conserva el texto y muestra qué corregir.
5. Si tu modelo requiere variables enteras (`integer`), binarias (`binary`) o cotas distintas de `[0, +inf)`, cambia a **Modo Tabla** y ajusta **Tipo**, **Mín** y **Máx** en las variables detectadas (además del título y descripción).

---

## Incorporar un ejercicio a la carpeta compartida

1. Diligencia el ejercicio, verifica que se pueda abrir y resolver con **Formular → Cargar ejercicio**, y compártelo con quien administra el repositorio.
2. Para incorporarlo de forma permanente en [`ejercicios/`](../ejercicios/), se puede guardar directamente el `.xlsx` en dicha carpeta o añadir su JSON en [`examples/`](../examples/) (usando [Producción de papel](../examples/06_produccion_papel.json) como referencia) y regenerar los `.xlsx` con `python3 scripts/build_excel_templates.py`.

## Revisar entregas y exportar resultados

En **Explorar resultados**, elige **Copiar para informe**, **Excel (.xlsx)** o **PDF** en la parte superior. Los dos archivos incluyen las figuras aplicables a las dimensiones y resultados del modelo. La aplicación y el informe indican qué figura no se pudo generar.

El PDF reúne la formulación, las tablas de resultados y las gráficas en un informe paginado. Para revisar o modificar una entrega, abre el `.xlsx` con **Formular → Cargar ejercicio**. El libro incorpora las siguientes hojas.

1. **`Resumen_Ejecutivo`**: Presenta metadatos del ejercicio (título, descripción, fuente académica, número de variables/objetivos/restricciones), el vector de pesos aplicado, el estado de verificación del solver (`optimal` o `partial`), el Punto Ideal ($Z^*$), el Nadir aproximado ($Z_{\text{peor}}$) y la síntesis de métricas.
2. **`Matriz_de_Pagos`**: Matriz cuadrada $q \times q$ donde cada fila muestra los valores de todos los criterios al optimizar un objetivo individual en solitario. Incluye filas de referencia para Ideal ($Z^*$) y Nadir aproximado, además del rango y fuente de normalización de cada objetivo.
3. **`Soluciones_Compromiso`**. Columnas `Métrica`, `Estado`, `Distancia D_p`, una por variable y cuatro por objetivo con los prefijos `Z:`, `% Logro:`, `Desviación:` y `Brecha ponderada:`. Hay una fila por métrica.
4. **`Frontera_Pareto`**. Cuando hay muestras, presenta `#`, `Métrica`, `Estado`, los valores por objetivo y las cantidades por variable.
5. **`Modelo`**. Tabla estandarizada (`Meta`, `Variable`, `Objetivo`, `Restriccion`) que se puede volver a abrir mediante **Cargar ejercicio**. Al cargar, las binarias toman el dominio [0, 1]. Para fijarlas, agrega una restricción de igualdad en el modelo.
6. **Hojas de gráficas**. Incluyen una imagen por vista aplicable, con sus ejes, leyenda y descripción.
