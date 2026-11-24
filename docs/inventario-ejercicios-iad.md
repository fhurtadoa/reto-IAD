# Inventario de materiales académicos revisados

Revisión de la carpeta local `IAD`. Se priorizaron enunciados y notebooks de formulación continua. Los materiales se referencian por nombre y tema. El repositorio contiene las plantillas de OptiCompromise y el modelo transcrito.

| Material | Estructura encontrada | Resultado |
|---|---|---|
| Taller 1, Formulación de problemas multiobjetivo, «Producción de papel» | 12 variables de toneladas para 3 máquinas y 4 papeles, costos y calidad por tonelada, 3 tiempos disponibles y 4 demandas mínimas. | Incorporado. Tasas convertidas a tiempo unitario y unidades documentadas. |
| Taller 1, «Diseño óptimo de un contenedor» | Dos dimensiones, costo y peso en función de las áreas. Volumen fijo de 10 m³ que multiplica dimensiones. | Incompatible con el motor lineal. |
| Taller 1, «Problema del transporte» | 3 orígenes y 4 destinos, 12 flujos, costo y riesgo, capacidades y demandas. | Compatible. Ya existe como ejercicio de Transporte con los datos base. |
| Taller 1, «Cadena de distribución con dos eslabones» | Flujos planta–bodega y bodega–región, capacidades, demanda, deterioro y tiempos por trayecto. | Compatible si el tiempo se agrega como días por caja. Queda por confirmar qué significa «tiempo total de entrega» en el enunciado. Sin transcribir. |
| Taller 2, introducción y notebook para estudiantes sobre costo y riesgo | Óptimos independientes y cruce de soluciones. Ajuste coordinado de oferta O1 y demanda D2 por un dígito. | Compatible. Reutiliza Transporte y aplica los cambios de la instancia antes de resolver. |
| Taller 3, métodos continuos y notebook `Problema_tte_MO_Compromiso.ipynb` | Producción de papel con demanda de Prensa y pesos parametrizados. Transporte resuelto de apoyo. | Los tres métodos de compromiso son compatibles. La guía explica cómo ingresar el parámetro. El taller pide aparte la comparación con factores ponderantes. |
| Clase 15, planificación de Celdas Fotovoltaicas | Dos cantidades continuas, utilidad y contaminación, cotas y restricciones lineales. | Ya disponible como ejemplo y prueba de referencia. |
| Taller de compromiso discreto, notebook de carros eléctricos y dominancia | Matriz de consecuencias de alternativas finitas y ranking multicriterio. | Fuera del flujo de plantillas continuas. |
| Taller y notebook AHP de carros | Jerarquía y matrices de comparaciones pareadas. | Fuera del método y del formato del catálogo. |
| Notebooks de viabilidad del nuevo producto y predicción de demanda de vuelos | Nodos de azar y decisión, o predicción con red neuronal y simulación. | Fuera del alcance del motor. |

Las referencias de Curso y Clase 15 corresponden al material revisado en la auditoría anterior. Se utilizó OpenAI Codex para inventariar los materiales, transcribir el modelo lineal de papel, implementar el catálogo y las ayudas de interfaz, y comprobar los resultados.
