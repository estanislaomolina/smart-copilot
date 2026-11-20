# Auditoría inicial del dataset

El CSV de SOFLEX (`data/raw/dataset_challenge_soflex.csv`) permite desarrollar y demostrar el prototipo, pero sus etiquetas no deben utilizarse como verdad incuestionable para evaluar extracción. Hay información enriquecida respecto del relato y formatos que requieren un modelo de ubicación más expresivo que una altura numérica.

## Reproducción

Requiere Python 3.10 o superior y solo su biblioteca estándar. Desde la raíz:

```bash
python3 scripts/audit_dataset.py
python3 scripts/audit_dataset.py --json
```

Se puede pasar la ruta de otro CSV con el mismo esquema como argumento posicional. El script solo lee el archivo y escribe el reporte en stdout; no modifica ni genera una versión corregida.

El modo JSON incluye hallazgos por registro y un SHA-256 del archivo. El orden es estable y no se incluyen timestamps de ejecución. Códigos de salida: 0 si no hay errores de estructura o valores, 1 si se detectan esos errores y 2 si no se puede leer o interpretar el archivo. Las señales heurísticas de revisión no producen por sí solas un error.

La versión visual está en `notebooks/data_exploration.ipynb`: no define funciones ni repite reglas de auditoría. Las tablas y gráficos se preparan en `scripts/explore_dataset.py`; sus dependencias opcionales están en `notebooks/requirements-notebook.txt`.

El original se conserva en `data/raw/` y los casos propios en `data/synthetic/`. Su traslado desde la raíz conserva los mismos bytes y el SHA-256.

## Resultado sobre el original

SHA-256: `14dd1776639625672c2475033b1bc9ba6ea817001fae6214e404d43cf4887d34`.

- 30 registros y 18 columnas; sin celdas vacías ni duplicados de ID o relato tras normalización.
- Seis categorías: incendio/rescate 8, emergencia médica 6, accidente vial 5, defensa civil 5, servicios públicos 4 y convivencia/seguridad 2.
- 30 subcategorías distintas, una muestra por cada una.
- Prioridades: P1 14, P2 12, P3 4; P4 sin cobertura.
- Relatos de 242 a 346 caracteres: cortos y poco representativos de conversaciones extensas.
- Cero errores detectados por las comprobaciones implementadas; esto no certifica la corrección semántica.
- Nueve alturas numéricas no aparecen como token en el relato.
- Doce valores de altura tienen contexto, referencia kilométrica o S/N.
- Las listas de preguntas no forman una partición literal de obligatorias menos respondidas en los 30 registros.

El script genera 124 señales: 9 de altura sin coincidencia, 12 de formato de altura, 34 de partes de intersección, 39 de calle o barrio/comuna y 30 de checklist. Una fila puede tener varias señales; no son 124 errores ni 124 casos distintos. No se usa ese conteo como métrica de calidad.

La búsqueda ignora tildes, puntuación y espacios, pero no interpreta sinónimos, abreviaturas ni geografía. Por ejemplo, “Av. Raúl Scalabrini Ortiz” puede ser una normalización de “Scalabrini Ortiz”. Comparar el barrio y la comuna completos también marca enriquecimientos esperables. Los flags sirven para dirigir revisión manual, no para rechazar etiquetas automáticamente.

## Revisión puntual y consecuencias

**SFX-REC-2026-001.** El relato dice “Av. Corrientes 1540 casi Montevideo”; la etiqueta incluye “Montevideo y Paraná”. Paraná no está en la transcripción. La extracción debe preservar Montevideo como referencia y no inventar la segunda calle. Un enriquecimiento externo, si se incorpora, necesita procedencia separada.

**SFX-REC-2026-018.** El relato ubica el hecho en Billinghurst y Gorriti, sin altura. La etiqueta agrega 1100 y Honduras. El resultado esperado para extracción textual debe admitir altura desconocida. Además, “monopatín o bicicleta” es ambiguo: la subcategoría de ciclista no resuelve esa incertidumbre por sí sola.

**Checklist del caso 001.** Se pregunta obligatoriamente por personas atrapadas, gas activo e inmuebles linderos. Solo está respondida la primera. Sin embargo, “pendientes” incluye corte de gas y humo en pisos superiores. Las columnas mezclan preguntas adicionales con el estado de las obligatorias. Se necesitan preguntas identificables y estado con evidencia; la revisión semántica completa del catálogo sigue pendiente.

**Ubicación.** Los casos 006 y 029 usan kilómetros; 008 y 022 usan S/N. “Altura” no debe ser un entero obligatorio. Calle y número tampoco cubren por sí solos estaciones, intersecciones y referencias de autopista.

## Uso de las columnas

- **Entrada principal de extracción:** `transcripcion_cruda`. Origen y timestamp pueden ser metadatos explícitos, no hechos inferidos del relato.
- **Identidad y trazabilidad:** `id_registro`, `timestamp_llamada` y `origen_reporte`.
- **Referencias a revisar:** categoría, subcategoría, prioridad, calle, altura, intersección, barrio/comuna, respuestas, pendientes, riesgos y notas. No entregar estos resultados al extractor como si fueran parte de la llamada que se evalúa.
- **Candidatas a catálogo:** preguntas mandatorias e instrucciones de prearribo, con procedencia y revisión. No se presentan como procedimientos validados para uso real.
- **Fuera de la decisión del operador:** recursos recomendados de despacho. No automatizar su envío.

Las preguntas respondidas y pendientes dependen del caso, por lo que no se deben copiar como estado inicial desde un catálogo. Un resumen generado también debe limitarse a información respaldada, aunque las notas del CSV incluyan enriquecimientos.

## Casos sintéticos y separación de usos

Los 30 registros provistos ya fueron inspeccionados y se consideran material de desarrollo y demostración. No se reportarán como una evaluación independiente ni se aplicará una división aleatoria que deje una sola muestra por subcategoría entre conjuntos.

`data/synthetic/development.json` contiene ocho especificaciones de comportamiento propias: dirección base, cambio de altura, altura ausente, negación, corrección, ambigüedad, instrucciones dentro del relato y número en palabras. Incluyen valores esperados y evidencia para revisión del usuario. Son datos de desarrollo, no resultados de un modelo ni casos reservados.

Los nombres de campos de esas expectativas son orientativos hasta definir los contratos; no imponen el esquema de la futura API. Una negación describe lo que reporta el llamante: “no veo personas” no confirma que el edificio esté vacío.

No se asignan prioridades ni indicaciones médicas nuevas. Para evaluarlas hace falta una rúbrica o catálogo revisado; otro LLM no es una fuente suficiente de verdad.

Los casos reservados se crearán en el hito de evaluación, tras fijar una primera versión del mock, prompt y contratos. Se registrará su versión y se evitará usarlos para ajustar reglas o recuperarlos como ejemplos. Si un error reservado se usa para corregir la implementación, ese caso pasa a ser regresión y se necesita un conjunto nuevo para una evaluación independiente. Los reportes identificarán qué casos y proveedor se usaron.

## Pendiente

La auditoría automática y esta revisión puntual no validan todo el catálogo ni la severidad sugerida. Quedan por acordar los contratos, revisar preguntas e instrucciones, aprobar las expectativas sintéticas e implementar y evaluar los proveedores.
