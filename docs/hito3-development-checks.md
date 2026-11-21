# Comprobaciones de desarrollo del proveedor real

Fecha: 2026-11-21. Configuración: Groq, openai/gpt-oss-120b, reasoning_effort=medium.
Este registro describe comprobaciones puntuales; no mide precisión ni sustituye una evaluación reservada.
No se ejecutó la corrida de los 30 registros.

## Negativas y dirección nueva — comprobación real

Entrada propia de desarrollo, definida antes de consultar al modelo:

> Llamante: Hay fuego en un depósito de calle Las Heras 820, cerca del cruce con Rivadavia. Todos salieron y pueden alejarse por sus propios medios. No hay nadie atrapado ni personas heridas.

Con incident-v5, ambas peticiones devolvieron HTTP 200. La extracción devolvió calle Las Heras, altura 820 e intersección Rivadavia; localidad desconocida.
El checklist de la guía general marcó atrapados y heridos/peligro como respondidas negativamente, y ubicación como respondida, con evidencia.
No se usó esta entrada para añadir reglas al Mock.

## Corrección posterior — ubicación y checklist comprobados puntualmente

Entrada propia preparada para verificar que una dirección nueva reemplace la anterior:

> Llamante: Hay humo en Belgrano 230, esquina Mitre. No sé si quedó alguien dentro.
> Operador: Confirme la dirección y si hay personas adentro.
> Llamante: Me equivoqué de dirección: es San Martín 480, casi Sarmiento. El encargado acaba de salir, ya no queda nadie dentro. No hay heridos.

Se espera dirección San Martín 480 con transversal Sarmiento, sin conservar Belgrano ni Mitre como ubicación vigente. La salida del encargado y la negativa deben actualizar el checklist con evidencia posterior.
La consulta con incident-v5 devolvió HTTP 429. Un intento posterior con incident-v6 también devolvió HTTP 429. Se detuvieron esas consultas. En una comprobación posterior acotada se obtuvo la ubicación corregida; ver el registro siguiente.
La aplicación mostró el límite del proveedor; no cambió a Mock silenciosamente.

## Conservación de decisiones — replay controlado

Se reutilizó la respuesta real del primer caso, sin nuevas consultas al proveedor:
se fijaron manualmente altura 822, prioridad P2 y una respuesta ambigua de atrapamiento.
El helper real del frontend conservó esos tres datos y emitió dos avisos por diferencias de altura y prioridad.
El motor de protocolos recibió un evaluador de replay de las respuestas obtenidas, conservó la respuesta manual y señaló la discrepancia.
El snapshot se guardó y recuperó idéntico con CallStore en SQLite temporal.
Esta comprobación valida combinación, conflictos y persistencia; no demuestra que el LLM interprete una conversación posterior correctamente. No se modificó la base de llamadas del usuario.

## Intersecciones y ajuste pendiente de comprobar

En el incendio usado previamente en desarrollo, el modelo dejó desconocida una transversal presente en el relato.
La conversión local copia el campo estructurado; no elimina esa información. El caso nuevo anterior sí extrajo una transversal.
incident-v6 pide revisar todos los componentes explícitos de la dirección vigente y no mezclar componentes descartados al corregirla.
No incorpora nombres de calles, expresiones regulares, IDs ni respuestas del CSV. No garantiza que el modelo deje de omitir datos. Una comprobación posterior devolvió correctamente calle, altura y transversal corregidas; todavía no mide consistencia ni generalización.
Las citas exactas y los contratos estructurales tampoco garantizan que la interpretación sea correcta.

## Verificaciones técnicas

Pasaron 73 pruebas Python, cinco del frontend y el build. Docker Compose reconstruyó y arrancó la aplicación con el prompt actualizado.
Estas pruebas técnicas son distintas de las comprobaciones semánticas reales. No se añadieron pruebas por cada transcripción ni se modificaron las reglas del Mock.

## Preparación reproducible posterior

Los dos relatos anteriores y sus expectativas se registraron en data/evaluation/development.json, separados del CSV original y de los ocho casos sintéticos previos.
El comando python3 scripts/evaluate.py --provider mock completó ambos casos, con diferencias en ambos: el Mock omite la transversal del primer relato, no resuelve la corrección del segundo y presenta otras diferencias de formato y checklist.
El reporte literal no distingue por sí solo equivalencia semántica de errores reales. No se ajustaron reglas para hacerlo coincidir.
Se verificó con tres pruebas del evaluador que las expectativas quedan locales, una pregunta ausente no cuenta como pendiente correcta y un 429 detiene los casos restantes sin copiar mensajes remotos al reporte.
El total actual es 76 pruebas Python. No se ejecutó el nuevo comando con Groq ni se hicieron más consultas externas durante este incremento.

## Reanudación conservadora de Groq

Por autorización del usuario se hicieron exactamente dos consultas adicionales de extracción, secuenciales, con max_retries=0, al mismo caso de corrección ya definido. No se ejecutó el checklist ni la batería completa.
La primera terminó como invalid_provider_output; no se aceptó la salida. El diagnóstico conservado no permite identificar la causa precisa de ese fallo.
La segunda devolvió HTTP 200 y pasó los contratos y la evidencia literal: calle San Martín, altura 480 e intersección Sarmiento. Referencia y localidad quedaron desconocidas. No arrastró Belgrano ni Mitre a esos campos.
Los encabezados de la segunda respuesta indicaron 998 solicitudes diarias restantes y 5254 tokens por minuto restantes en ese instante. Son contadores de ventanas distintas, no una estimación de tokens diarios disponibles.
Esto confirma que Groq volvió a aceptar solicitudes; no identifica retrospectivamente qué límite causó los 429 anteriores.
La corrección de ubicación quedó comprobada en una salida válida, con un intento inválido previo también registrado. Se detuvieron las consultas tras esos dos intentos; el checklist se comprobó en el incremento siguiente.

## Checklist posterior y continuidad manual

Se hizo una única consulta adicional a Groq con max_retries=0, reutilizando la extracción válida anterior. No se volvió a ejecutar la extracción.
El checklist pasó los contratos y las verificaciones de evidencia literal:
- Atrapados: answered, respuesta «no», sustentada en que ya no queda nadie dentro.
- Heridos o en peligro: ambiguous; «No hay heridos» no descarta que haya personas en peligro.
- Ubicación: answered, San Martín 480, casi Sarmiento.

Revisión de expectativas: el archivo de desarrollo esperaba «No» para la pregunta compuesta sobre heridos o peligro. Esa expectativa era demasiado fuerte: el relato no descarta la segunda condición. Se cambió a ambiguous sin exigir un texto de respuesta. No se cambió el modelo, el prompt ni el Mock para reproducir una salida. Esta revisión posterior pertenece al desarrollo y descarta presentar este caso como evaluación independiente.

Sin más consultas, se comprobaron appendTurns, mergeReviewedData y nextGuidanceQuestion del frontend con las respuestas reales. Anexar los turnos reconstruyó exactamente el relato, manteniendo el prefijo. La próxima pregunta fue la ambigua.
Para provocar un conflicto se construyó un estado manual anterior con calle Belgrano, prioridad P2 y respuesta afirmativa a atrapados. La combinación conservó esas decisiones y avisó las discrepancias; no las reemplazó por el resultado automático.
El motor recibió un replay del checklist real, conservó la respuesta humana y emitió un aviso. SQLite temporal recuperó el snapshot idéntico, con preguntas iguales en la carta y el protocolo. Esta parte es una simulación local de continuidad, no otra inferencia real ni una prueba del navegador.

Estado: la integración del Hito 3 tiene las comprobaciones puntuales previstas. Hubo una salida inválida rechazada y se registran limitaciones. La evaluación de consistencia, generalización y afirmaciones sin respaldo continúa en el Hito 4; no hay una métrica de precisión ni un conjunto reservado ejecutado.
