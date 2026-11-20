# Riesgos y prioridad del mock

El mock ahora completa `data.risks` y `data.priority` mediante reglas explícitas de simulación. La API conserva el mismo contrato. No se leen las etiquetas del CSV durante el análisis, no se agregan dependencias y no se usan los ocho casos sintéticos apartados.

La ampliación del mock queda acotada a la demostración. El proveedor real se retomará con Haiku después de completar el flujo del operador.

## Recorrido técnico

`MockExtractionProvider.analyze()` obtiene los turnos del llamante, extrae ubicación y categoría, llama a `extract_risks()` y después a `suggest_priority()`.

- `backend/domain/transcript.py`: segmentación y offsets compartidos; se trasladaron sin alterar su comportamiento.
- `backend/providers/mock_rules.py`: reglas, referencias a casos de desarrollo y decisión de prioridad.
- `backend/providers/mock.py`: integra los resultados en `AnalysisResult`.
- `tests/test_mock_priority_risks.py`: valores esperados, negaciones, incertidumbre, correcciones y decisión aislada de las expresiones regulares.

`model=rules-v2` identifica esta versión. Los IDs de reglas aparecen en `rationale`; su campo `source_cases` en el código permite rastrear qué registros se usaron como referencia. Los IDs de referencia no se usan para reconocer una llamada.

## Riesgos con evidencia

Quince reglas reconocen señales acotadas: fuego, personas dentro del lugar, humo, ascensor trabado, dificultad respiratoria, gas, cable chispeando, derrame de combustible, convulsión, atrapamiento vinculado a vehículo, traumatismo, desprendimiento estructural, agua en subsuelos, fuego en contenedor y semáforos apagados.

Se devuelven como inferencias y con texto/offsets verificables. No se copian diagnósticos o detalles añadidos en `riesgos_detectados`: por ejemplo, del caso 009 se devuelve “Posible dificultad respiratoria”, no “hipoxemia pediátrica”.

## Reglas de prioridad de simulación

Se diseñaron trece reglas sobre señales reconocidas:

- `P-FIRE-TRAPPED`: fuego y personas posiblemente dentro → P1; referencia 001.
- `P-BREATHING`: señal de dificultad respiratoria → P1; referencias 009 y 019.
- `P-GAS`: escape de gas reconocido → P1; referencia 012.
- `P-LIVE-CABLE`: cable con chisporroteo → P1; referencia 020.
- `P-FUEL`: derrame de combustible reconocido → P1; referencia 022.
- `P-CONVULSION`: convulsión reportada → P1; referencia 026.
- `P-VEHICLE-TRAPPED`: atrapamiento vinculado a vehículo → P1; referencias 018 y 029.
- `P-ELEVATOR`: ascensor trabado y categoría incendio/rescate → P2; referencia 003.
- `P-INJURY`: traumatismo reconocido y categoría médica → P2; referencias 010 y 023.
- `P-STRUCTURE`: desprendimiento y categoría defensa civil → P2; referencias 014 y 027.
- `P-INDOOR-FLOOD`: agua en subsuelos y categoría servicios públicos → P2; referencia 028.
- `P-CONTAINER`: fuego en contenedor y categoría incendio/rescate → P3; referencia 002.
- `P-SIGNALS`: semáforos apagados y categoría servicios públicos → P3; referencia 024.

Son aproximaciones para reproducir escenarios del material sintético, no reglas de triage ni protocolos operativos validados. No se asigna una prioridad solo por pertenecer a una categoría.

Cuando coinciden varias reglas se conserva la mayor prioridad reconocida, con evidencia y justificación de las reglas seleccionadas; los demás riesgos se mantienen. Las señales específicas P1 pueden producir una sugerencia aunque la categoría esté desconocida, como el derrame del caso 022. Las reglas P2/P3 requieren además la categoría indicada.

Sin regla aplicable, la prioridad queda desconocida. No hay fallback a P3/P4 ni reglas P4: el CSV no aporta ejemplos para justificarlas. Un número de coincidencias no se presenta como probabilidad de acierto.

## Negaciones y cambios de relato

La interpretación es local a cláusulas y considera turnos del llamante:

- Una negación simple no produce un riesgo afirmativo: “no hay fuego”.
- Incertidumbre o una pregunta del llamante sobre la señal deja ese riesgo sin resolver.
- Afirmaciones positivas y negativas de una misma señal, sin corrección explícita, se tratan como contradicción.
- “Perdón”, “corrijo” y otras marcas reconocidas permiten reemplazar menciones previas de esa señal.
- Si queda alguna señal ambigua o contradictoria, la prioridad automática se bloquea, incluso si otra regla de menor prioridad podría aplicar.

Las marcas y expresiones soportadas están en el código. Esto no resuelve de forma general temporalidad, distintos sujetos, citas, negaciones complejas ni errores de transcripción. Las reglas de ubicación y categoría conservan su alcance anterior; esta mejora no las convierte en comprensión semántica general.

## Cobertura y verificación

Se comparan prioridades explícitas con las referencias revisadas de 17 llamadas conocidas del CSV: 001, 002, 003, 009, 010, 012, 014, 018, 019, 020, 022, 023, 024, 026, 027, 028 y 029. Las otras 13 quedan sin prioridad en esta versión. Es cobertura de desarrollo, no una medición independiente de generalización.

La suite también comprueba retractaciones, confirmaciones, cambios de orden, separación entre señales negadas y afirmadas, offsets de todos los campos, y el recorrido HTTP hasta riesgos/prioridad. El test anterior que exigía esos campos vacíos se reemplazó por invariantes de procedencia/evidencia y por expectativas concretas para el nuevo comportamiento.

```bash
python3 -m unittest discover -s tests -v
```

Verificación realizada: 35 tests pasan. Se construyó y arrancó el contenedor con healthcheck saludable y se enviaron peticiones HTTP reales para los casos 001, 002, 003, 022 y 008, comprobando P1/P3/P2/P1/desconocido. Una variante contradictoria del caso 026 produjo prioridad desconocida y advertencia.

La evaluación con llamadas nuevas y la revisión de dominio siguen pendientes. No se agregan protocolos, instrucciones de prearribo, panel ni persistencia; el Hito 2 permanece abierto.
