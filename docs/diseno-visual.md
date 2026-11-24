# Sistema visual de OptiCompromise

La vista de método se lee en tres pasos. Referencias presenta la matriz de pagos y sus vectores en una sola tabla. Normalización muestra las fórmulas, la escala que usa el motor y un ejemplo del modelo abierto. Métricas explica el objetivo de cada distancia y cómo se linealiza el minimax. Los dos desplegables contienen la matriz normalizada y el desarrollo de las restricciones por objetivo, útiles para comprobar el cálculo después de leer el recorrido principal.

| Elemento | Regla |
|---|---|
| Paleta | Azul tinta para texto, gris azulado para contexto y fondos de lectura, y vino para subtítulos, selección y navegación. Ámbar identifica el ideal en la matriz. Verde, ámbar y rojo siguen identificando estados del solver y se acompañan de texto. |
| Jerarquía | Geist para interfaz y KaTeX para notación. Los títulos identifican la tarea. Los subtítulos en vino explican el propósito. Las tablas usan cifras tabulares y texto de 13 px. |
| Espaciado | Unidad base de 14 px. La guía se apoya en una superficie continua y separadores entre pasos. Los paneles de fórmulas y métricas comparten el fondo secundario. |
| Tablas | Encabezados descriptivos, filas de referencia rotuladas y desplazamiento horizontal local. Cada tabla ancha puede recibir foco con el teclado. |
| Interacción | Un borde de foco azul distingue el teclado del estado activo en vino. Los enlaces internos identifican las secciones. El gráfico mantiene un espacio fijo para el estado de cálculo. |
| Tema oscuro | Los mismos roles cambian de valor en los tokens CSS. El acento de los subtítulos es rosa claro y conserva su jerarquía sobre el texto y el fondo. |

Los tokens viven en `web/app/globals.css`. `SectionHeading` unifica título y subtítulo en Método, Formulación, Preferencias y Resultados. `MethodGuide` reutiliza los datos de la respuesta del solver y el generador de fórmulas minimax que ya usa el proyecto.

Se usó OpenAI Codex para inspeccionar el diseño, implementar el recorrido, refinar estilos y verificar el comportamiento en el navegador. El trabajo se limita al frontend y a su documentación.
