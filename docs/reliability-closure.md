# Cierre técnico: recuperación parcial y reutilización de evidencia

## Comportamiento (incident-v9)

La extracción conserva cada campo que pasa los contratos y la comprobación literal de evidencia.
Un campo inválido queda desconocido; una señal inválida se elimina. El panel muestra un aviso visible;
las rutas descartadas quedan en las advertencias desplegables y el reporte de evaluación.
No se publican valores rechazados ni se aproxima una cita.
JSON roto, estructura incompleta, propiedades raíz ajenas, rechazos, truncamiento y resultados completamente
inutilizables siguen siendo errores. Una salida parcial se registra como `partial`, separada de `valid`.
Esto mejora la continuidad, no certifica que una interpretación sea correcta.

La misma solicitud incluye las ocho preguntas distintas existentes en las seis guías generales, con sus
aclaraciones autorizadas. No incluye instrucciones operativas, ejemplos, IDs de registros ni respuestas
esperadas. El extractor devuelve sus estados con evidencia. No se agrega un clasificador de prioridades.

El evaluador guarda esas respuestas validadas en memoria, con límite de 256 entradas por proceso.
La clave contiene el hash de la transcripción completa y la definición completa de la pregunta.
Al aplicar un protocolo, reutiliza solamente las coincidencias exactas y consulta únicamente las preguntas
faltantes. Una guía general completa puede resolverse con una solicitud remota; un protocolo específico,
una respuesta descartada, un reinicio o una expulsión del caché pueden requerir otra solicitud.
No se reutilizan estados ante un cambio de conversación ni por similitud del texto de la pregunta.
Las revisiones humanas conservan precedencia y los desacuerdos se señalan mediante el motor existente.
La memoria no sustituye SQLite: los resultados aplicados y las decisiones humanas siguen persistidos allí.

Se envían ocho preguntas en vez de tres preguntas después de extraer. La reducción de solicitudes
se verificó con transporte controlado; todavía no se midieron el consumo, la latencia ni la precisión
de este prompt con Groq. No se trasladan los resultados v8 a v9.

## Variaciones reproducibles sin costo

`scripts/evaluate_robustness.py` ejecuta Mock sobre el original y cuatro variantes deterministas:
minúsculas, espacios repetidos, muletillas y números de hasta cuatro cifras escritos en palabras.
Conserva roles y límites de turno, negaciones y correcciones. Las expectativas se copian sin ajustarlas
a los resultados. El CSV no cambia. Las variantes son desarrollo conocido, nunca un conjunto independiente.

~~~bash
python3 scripts/evaluate_robustness.py --csv data/raw/dataset_challenge_soflex.csv --output artifacts/evaluation/robustness-nueva.json --export-cases artifacts/evaluation/robustness-casos-nuevos.json
~~~

Las rutas de salida deben ser nuevas. El comando devuelve 1 si encuentra diferencias o errores;
hay que leer ambos conteos por separado. Se puede exportar la suite para el evaluador existente
y elegir expresamente Groq más adelante, con su presupuesto y límites. Este comando nunca consulta un LLM.

Resultado ejecutado: 150 evaluaciones locales (30 por grupo), cero errores de ejecución y diferencias
literales en los 150 casos. La categoría coincide en 28/30 originales y 24/30 con espacios repetidos;
las comparaciones de ubicación pasan de 42/90 originales a 25/90 con espacios y 18/90 con números escritos.
En minúsculas hay 0/90 coincidencias de ubicación. La prueba detecta fragilidad del Mock; no se modifican
sus reglas para perseguir las etiquetas. La selección de guías y los subtipos también limitan las
comparaciones completas. Los conteos incluyen anotaciones no validadas y diferencias de escritura:
no son precisión semántica. Ver [resumen íntegro por variante](robustness-mock-results.json).

La primera ejecución de preparación detectó dos problemas del generador: la muletilla no se insertaba
en roles escritos en la misma línea y no se convertían números seguidos de punto. Se corrigió el generador,
sin cambiar expectativas ni el Mock. El resultado documentado corresponde a
`artifacts/evaluation/closure-robustness-mock-v3.json`; los artefactos previos de preparación se conservan
localmente y no se mezclan con él.

## Verificación

92 pruebas backend y 5 pruebas frontend aprobadas; build TypeScript/Vite aprobado.
Imagen Docker construida y Compose validado. Un contenedor aislado, sin red ni volumen de la aplicación,
completó panel, análisis Mock, protocolo, guardado SQLite, revisión, derivación simulada y recuperación.
Las regresiones comprueban recuperación de dirección con un riesgo inválido, descarte de categorías y
procedencias inválidas, rechazo de estructuras rotas, una solicitud para extracción y guía general,
evaluación de preguntas faltantes, invalidación al cambiar texto/definición, límite de memoria y
precedencia humana. No son una evaluación de la comprensión del modelo.

No se realizaron nuevas solicitudes a Groq ni a Anthropic durante este incremento.
La corrida anterior y sus números reales se explican en [final-csv-run.md](final-csv-run.md#resultado-registrado-de-la-corrida-20bincident-v8).
