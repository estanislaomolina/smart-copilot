# Extracción mock inicial

Este documento registra el primer incremento. Ver las ampliaciones de [riesgos/prioridad](mock-priority-risks.md) y [catálogo/checklist](protocol-engine.md).

Este incremento agrega `POST /api/analyze` con extracción parcial de ubicación y sugerencia de categoría. El proveedor aplica reglas sobre la transcripción; no lee el CSV ni devuelve una fila por ID. Funciona sin credenciales ni servicios externos.

## Uso

Arrancar con `docker compose up --build` y enviar:

```bash
curl http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Llamante: En Av. Corrientes 1540 hay fuego."}'
```

El resultado conserva el texto original en `request.transcript`. En `data.location` se obtiene la ubicación reconocida; en `data.category`, una sugerencia con evidencia y justificación. `provider` es `mock` y `model` identifica las reglas como `rules-v1`.

## Reglas y límites

- Si hay etiquetas de hablante, se procesan los turnos `Llamante:`; las preguntas de `Operador:` no se toman como hechos. Sin etiquetas, todo el texto se considera relato.
- Se reconocen algunos formatos de calle y altura, cruces, “casi”, “entre” y referencias de avenida o autopista. Los nombres propios deben seguir una capitalización reconocible. No se resuelve geografía, alias ni normalización fonética.
- Se preservan nombres del relato: no se agrega “Av. Raúl” a “Scalabrini Ortiz”, ni se completan barrios, comunas o alturas externas.
- Las correcciones numéricas simples se aceptan cuando están junto a la altura previa o indican explícitamente “altura correcta es”. Incertidumbre o varias alturas sin resolución dejan el número desconocido.
- Una coincidencia de nombre y número necesita prefijo de calle o contexto de ubicación; un nombre de persona y su edad no bastan.
- La categoría se infiere por coincidencias léxicas. Hay un filtro local de negaciones simples. Si aparecen señales de varias categorías, se devuelve desconocida con advertencia.
- Cada evidencia se obtiene del texto original, manteniendo sus offsets. La validación del contrato no prueba que la interpretación sea correcta.
- Prioridad, riesgos, subcategoría, resumen, distrito y preguntas quedan sin completar. Todavía no se seleccionan protocolos ni instrucciones.
- No hay persistencia, panel, revisión humana ni derivación implementados en este incremento.

Las reglas tienen cobertura limitada: no constituyen un parser general ni una clasificación operativa validada. Por ejemplo, el derrame de cisterna del caso 022 activa señales de accidente e incendio/rescate y queda pendiente de confirmación. Algunas referencias de estación o viaducto tampoco se reconocen. No se promete coincidencia con todas las etiquetas del CSV.

## Errores HTTP

Entrada vacía, texto de más de 50.000 caracteres, campos extra o JSON inválido producen 422 con `code=invalid_input`. No se repiten valores de entrada en los errores.

Los fallos esperados del proveedor se traducen a 503 (no disponible), 504 (timeout) o 502 (salida inválida). Una salida malformada o que cambia el texto de entrada tampoco se devuelve como éxito. Las pruebas simulan esos fallos; el mock no realiza llamadas de red que puedan producirlos.

## Pruebas reproducibles

Se usa unittest de Python y httpx para el cliente de pruebas HTTP. En un entorno virtual de Python 3.12:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

Las dependencias de desarrollo no se incluyen en la imagen de ejecución.

- Comparación de valores esperados de calle, altura, intersección y categoría para 12 llamadas del CSV, cubriendo las seis categorías. Las expectativas están en `tests/test_mock_analysis.py`, revisadas contra el relato y no contra etiquetas enriquecidas.
- En particular, 001 conserva Montevideo sin añadir Paraná; 003 no agrega Juncal/French; 005 y 018 mantienen altura desconocida en esquinas; 002 conserva el nombre de calle usado por el llamante.
- Comprobación de contrato, evidencia y repetibilidad sobre los 30 relatos originales. Esto verifica estructura y trazabilidad, no exactitud semántica de todos los campos.
- Variaciones puntuales de los relatos originales para comprobar cambios de dirección, correcciones, cantidades de personas, nombres y edades, negaciones, datos en conflicto y texto sin etiquetas de hablante.
- Integración HTTP, entradas inválidas y fallos de proveedor con dependencias sustituidas.

Verificación realizada: 18 tests pasan, incluyendo los subcasos de valores revisados y las 30 transcripciones. También se construyó y arrancó el contenedor, se comprobó el healthcheck y se enviaron peticiones HTTP reales: el caso 001 devolvió ubicación/categoría y un JSON malformado produjo 422.

Son pruebas de desarrollo y regresión sobre material conocido, no una evaluación independiente. Los ocho casos de `data/synthetic/development.json` siguen apartados y no se usan. Los valores esperados nuevos se revisarán con el usuario; no se añaden etiquetas clínicas ni prioridades.

La ampliación de riesgos y prioridad se documenta por separado. El catálogo de protocolos, panel y persistencia siguen pendientes; el Hito 2 continúa abierto.
