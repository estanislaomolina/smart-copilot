# Catálogo y checklist de demostración

Este incremento continúa el Hito 2 con catálogo y checklist. El proveedor real con Haiku se incorporará después de completar el recorrido del operador. No se añadieron reglas de extracción para cubrir más filas del CSV.

## Responsabilidades

El mock interpreta la transcripción y entrega datos con evidencia. El motor de protocolos recibe esos datos, selecciona o propone un protocolo y reconstruye el checklist. Las respuestas manuales compatibles se conservan. El panel permite usar la siguiente pregunta y revisar los estados; persistencia y derivación de la carta siguen pendientes.

El motor no importa el proveedor mock ni el futuro LLM. La API de extracción no selecciona protocolos ni genera instrucciones.

## Catálogo y procedencia

`data/protocols/demo.json` contiene 30 protocolos y 90 preguntas, derivados del material sintético de SOFLEX. Cada protocolo tiene ID, versión, categoría, subtipo, registro fuente y estado `demo_unverified`.

El generador toma únicamente categoría, subcategoría, preguntas mandatorias e instrucciones de prearribo, además del ID para trazabilidad. No importa transcripciones, ubicación, prioridad, respuestas ni estados pendientes. La columna `preguntas_pendientes` tampoco se convierte automáticamente en preguntas universales del protocolo, porque mezcla interrogatorio adicional con información específica del caso.

```bash
python3 scripts/build_protocol_catalog.py
```

El resultado es reproducible y el original no se modifica. El catálogo se valida al arrancar la API y se copia a la imagen; el CSV original no es necesario durante la ejecución.

Las instrucciones conservan el texto provisto y su fuente. El estado `demo_unverified` debe ser visible al presentarlas: no están validadas para uso operativo. Seleccionar un protocolo no equivale a aprobar clínicamente su contenido.

## Selección

- Categoría conocida sin subtipo resuelto: guía general definida para esa categoría, con `selection=general` y `selection_origin=category`. Las opciones de subtipo son opcionales.
- Categoría desconocida: selección pendiente, sin asumir una categoría ni elegir el primer candidato.
- Categoría y subtipo con coincidencia única en el catálogo: protocolo sugerido, todavía sujeto a revisión.
- ID de protocolo seleccionado explícitamente: selección del operador.
- Si el protocolo elegido contradice una categoría conocida, se devuelve 409 para revisar los datos. Si la categoría es desconocida, se permite la selección explícita con advertencia.
- Un ID inexistente produce 404.

El ID del protocolo sirve para seleccionar contenido del catálogo, no para reconocer una llamada ni obtener respuestas de una fila del CSV.

## Checklist

La selección y la evaluación de preguntas están separadas. `ProtocolEngine` recibe un `ChecklistEvaluator`; tras seleccionar el protocolo solicita evaluar su lista completa contra la conversación. Se validan la estructura Pydantic, el conjunto exacto de IDs, textos inalterados, aclaraciones del catálogo y evidencia literal. El evaluador no puede atribuir revisiones al operador. Se evalúa antes de combinar las revisiones humanas, que siguen teniendo precedencia.

El evaluador actual es `MockChecklistEvaluator`, con alcance limitado:

- Para cualquier pregunta conserva el reconocimiento anterior de pregunta explícita del catálogo y respuesta inmediata.
- Para la pregunta sobre personas atrapadas reconoce algunas afirmaciones y negaciones espontáneas generales, incertidumbre y correcciones explícitas. No usa IDs de llamadas ni incorpora nombres de ocupaciones.
- Reutiliza la señal existente de posible presencia de personas dentro como información relacionada: estar dentro no demuestra estar atrapado. El caso 001 queda ambiguo con la cita «adentro quedó el cocinero».
- Afirmaciones contradictorias siguen siendo ambiguas; una corrección explícita o una aclaración de una presencia anterior puede resolverlas según el repertorio limitado.
- No se interpretan arbitrariamente todas las preguntas ni todas las paráfrasis. Haiku aún no está implementado para este contrato.

Además del catálogo específico derivado del CSV, `data/protocols/general.json` define una guía general por cada una de las seis categorías. Tiene versión propia (`general-demo-v1`) y procedencia de curaduría del prototipo. No se genera desde las filas del dataset ni mediante unión de instrucciones. El catálogo rechaza más de una guía general para la misma categoría y distingue `scope=general` de `scope=specific`. La selección general no confirma un subtipo ni los datos extraídos.

Las aclaraciones se registran aparte en `data/protocols/follow-ups.json`, versión `demo-follow-ups-v1`, con procedencia de curaduría del prototipo y sin validación operativa. Se vinculan por texto de pregunta al cargar el catálogo; no se modifica el CSV ni el catálogo generado. `ProtocolQuestion.follow_up` solo propone una aclaración autorizada cuando la evaluación es ambigua. La guía muestra su evidencia, prioriza la aclaración y permite copiarla al campo Operador. La respuesta posterior se evalúa sobre la misma pregunta original; no se crean respuestas por similitud con filas del CSV.

Al reaplicar un protocolo:

- Se conservan respuestas de origen `operator` con el mismo ID y texto compatible.
- Las respuestas automáticas se recalculan a partir del diálogo actual.
- No se transfieren respuestas manuales a preguntas distintas; se informa su falta de correspondencia.
- Se valida que la evidencia incluida corresponda al texto recibido.

El panel admite revisión manual de las preguntas. Una pregunta `pending` puede tener `origin=operator` y una justificación, sin respuesta ni evidencia: representa una reapertura explícita y se conserva al recalcular. Una respuesta manual `answered` exige texto; `ambiguous` y `not_applicable` exigen justificación. Solo se conservan revisiones cuyo ID y texto coinciden con la pregunta del catálogo.

`ProtocolResult.review_notices` informa diferencias de texto o estado entre el diálogo reconocido y una revisión manual conservada. El panel muestra estos avisos para solicitar revisión. Esta comparación conservadora no verifica contradicciones semánticas ni modifica la respuesta humana. El historial persistido de revisiones sigue pendiente.

## API

- `GET /api/protocols`: lista de protocolos; admite filtro `category`.
- `GET /api/protocols/{protocol_id}`: definición y procedencia del protocolo.
- `POST /api/protocols/apply`: recibe `request` y `data` del análisis, más un `protocol_id` opcional. También admite datos revisados por el operador.
- `POST /api/analyze` sigue entregando la extracción; se conserva la separación de responsabilidades.

Ejemplo mínimo de aplicación con categoría confirmada por el operador:

```json
{
  "request": {
    "transcript": "Llamante: Hay fuego. Operador: ¿Hay garrafas o cañería de gas activa? Llamante: No."
  },
  "data": {
    "category": {
      "value": "INCENDIO_RESCATE",
      "origin": "operator"
    }
  },
  "protocol_id": "sfx-demo-001"
}
```

La pregunta sobre gas queda respondida “No.” con evidencia; las otras dos siguen pendientes. Las instrucciones vienen del catálogo, con su estado de revisión, no del texto de la llamada.

## Verificación y siguiente paso

Se agregaron pruebas puntuales de reproducción del catálogo, exclusión de respuestas de referencia, selección pendiente, respuestas negativas/ambiguas, contradicciones/correcciones, conservación de revisión manual y errores HTTP.

```bash
python3 -m unittest discover -s tests -v
```

Verificación inicial, anterior a las guías generales: pasaban 41 tests en total. Docker construye y arranca el servicio con el catálogo incluido. Se comprobaron peticiones HTTP reales para listar candidatos, aplicar un protocolo, conservar una respuesta negativa con evidencia y dejar pendiente una selección sin subtipo, comportamiento reemplazado por la guía general por categoría.

Después del panel y la guía editable, restan confirmaciones individuales de campos y carta persistida. Después se retomará Haiku y se evaluará con material reservado; los 30 registros conocidos no se presentarán como evaluación independiente.
