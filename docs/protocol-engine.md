# Catálogo y checklist de demostración

Este incremento continúa el Hito 2 con catálogo y checklist. El proveedor real con Haiku se incorporará después de completar el recorrido del operador. No se añadieron reglas de extracción para cubrir más filas del CSV.

## Responsabilidades

El mock interpreta la transcripción y entrega datos con evidencia. El motor de protocolos recibe esos datos, selecciona o propone un protocolo y reconstruye el checklist. Las respuestas manuales compatibles se conservan. La pantalla, la persistencia y la derivación de la carta siguen pendientes.

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

- Categoría sola: selección pendiente y lista de candidatos, sin preguntas ni instrucciones de un protocolo elegido arbitrariamente.
- Categoría y subtipo con coincidencia única en el catálogo: protocolo sugerido, todavía sujeto a revisión.
- ID de protocolo seleccionado explícitamente: selección del operador.
- Si el protocolo elegido contradice una categoría conocida, se devuelve 409 para revisar los datos. Si la categoría es desconocida, se permite la selección explícita con advertencia.
- Un ID inexistente produce 404.

El ID del protocolo sirve para seleccionar contenido del catálogo, no para reconocer una llamada ni obtener respuestas de una fila del CSV.

## Checklist

Las preguntas empiezan pendientes. La implementación inicial reconoce preguntas explícitas del operador cuya formulación coincide con la del catálogo, ignorando tildes, puntuación y mayúsculas, y examina el turno siguiente del llamante.

Una respuesta afirmativa o negativa inequívoca a una única pregunta de sí/no se marca como respondida y conserva el contexto completo como evidencia. “No sé”, respuestas no interpretables, varias preguntas seguidas de un solo “sí”, o respuestas contradictorias quedan ambiguas. Una corrección explícita reconocida permite reemplazar las respuestas anteriores.

No se marca una pregunta como respondida porque coincida el incidente o porque el CSV de referencia la tenga respondida. Por eso el relato original del caso 001 conserva las preguntas pendientes: este motor todavía no interpreta automáticamente la respuesta implícita sobre el cocinero.

Las respuestas de texto libre y las formulaciones distintas requieren revisión manual en esta versión. La futura integración con Haiku podrá aportar interpretación contextual; este incremento no intenta resolverla con reglas por transcripción.

Al reaplicar un protocolo:

- Se conservan respuestas de origen `operator` con el mismo ID y texto compatible.
- Las respuestas automáticas se recalculan a partir del diálogo actual.
- No se transfieren respuestas manuales a preguntas distintas; se informa su falta de correspondencia.
- Se valida que la evidencia incluida corresponda al texto recibido.

El contrato admite datos y respuestas manuales, pero todavía no hay panel ni historial persistido de esas revisiones.

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

Verificación realizada: pasan 41 tests en total. Docker construye y arranca el servicio con el catálogo incluido. Se comprobaron peticiones HTTP reales para listar candidatos, aplicar un protocolo, conservar una respuesta negativa con evidencia y dejar pendiente una selección sin subtipo.

El siguiente incremento es la pantalla del operador con edición, confirmación y carta persistida. Después se retomará Haiku y se evaluará con material reservado; los 30 registros conocidos no se presentarán como evaluación independiente.
