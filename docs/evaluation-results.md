# Resultados de evaluación — tandas reservadas

Fecha UTC: 2026-11-21T21:38:53.607803+00:00. Código fijado en el commit f562623.
Conjunto: data/evaluation/holdout-v1.json, SHA-256 4afc6d9160783803ab67b24899ae7d7475624f59cf3667cb4de20bd50cecaf8a.
Se mantuvieron las expectativas, los prompts, las reglas y el catálogo sin cambios.

## Configuración y ejecución

Groq, modelo openai/gpt-oss-120b, prompt incident-v6, razonamiento medium.
Timeout de transporte: 20 segundos. Reintentos: cero.
Se seleccionó únicamente EVAL-01 con límite de un caso, antes de observar su salida. Los otros siete casos no fueron seleccionados.
Se ejecutó scripts/evaluate.py dentro del contenedor existente, con las credenciales de su entorno y PYTHONPATH=/app. El script y el conjunto se copiaron a /tmp; no se modificó la base de llamadas del usuario.

## Resultado

El caso terminó con invalid_provider_output en la extracción, tras una solicitud y sin reintentos.
La salida se rechazó y no se publicaron datos extraídos. El checklist no se inició.

Tiempo de extracción: 4.011781 segundos.
Tiempo total del análisis del caso: 4.011818 segundos.
Tiempo de checklist: no disponible, etapa no iniciada. No debe representarse como cero.

Conteo: un caso intentado, un error terminal de salida inválida; siete casos no seleccionados.
No hay comparaciones de ubicación ni de checklist, ni entradas de revisión semántica.
No se puede calcular precisión ni afirmar ausencia de alucinaciones a partir de esta salida rechazada. Tampoco hay medición de latencia de una ejecución exitosa.
El consumo de tokens no está disponible en el contrato. No se estimó.

## Limitaciones y continuación

El reporte conserva el código de error seguro, pero no identifica qué restricción exacta falló ni si el rechazo ocurrió en la generación remota o en la validación local. No se atribuye una causa sin evidencia.
No se repitió el caso para obtener un resultado favorable. Una nueva corrida deberá conservar este fallo en los resultados agregados e identificarse como otra ejecución.
La próxima tanda debe mantener la misma configuración y expectativas y seleccionar un caso pendiente; si se modifica el sistema usando resultados reservados, debe declararse el cambio y su efecto sobre la independencia de la evaluación.

El reporte completo permanece local e ignorado en artifacts/evaluation/groq-eval-01.json.
SHA-256 del reporte: 20b222878c859a85ce9adc4f483f8507e2f94317909baf5d4b250880f1c378c1.
Este documento contiene solo configuración y resultados resumidos, sin claves ni cuerpos de respuesta del proveedor.

## Segunda tanda — EVAL-02

Fecha UTC: 2026-11-21T21:48:31.866143+00:00. Mismo código de evaluación del commit f562623, conjunto congelado y configuración: Groq, openai/gpt-oss-120b, incident-v6, razonamiento medium, timeout 20 segundos, cero reintentos.
Se seleccionó únicamente EVAL-02, sin repetir EVAL-01. Se añadió observación local de estados HTTP y causas de validación para diagnóstico; no se modificaron solicitudes, prompts, reglas ni expectativas.

La extracción y el checklist devolvieron HTTP 200 y pasaron los contratos. Coincidieron las siete comprobaciones literales: categoría, calle, altura, transversal, localidad desconocida y estados de las dos preguntas esperadas.
El protocolo seleccionado fue general-accidente-vial. Ambas preguntas de seguridad recibieron respuesta negativa; la dirección se recuperó con la transversal informada.
La inspección asistida por el agente encuentra esas respuestas coherentes con el relato. Las ocho entradas del reporte siguen pendientes de revisión humana; no se presentan como una validación humana independiente ni se calcula una tasa de alucinaciones.

Tiempo de extracción: 2.971686 segundos.
Tiempo de checklist: 2.042708 segundos.
Tiempo total: 5.014527 segundos.
Solicitudes observadas: una de extracción y una de checklist. Reintentos: cero.
No se midió consumo de tokens ni latencia del navegador.

Reporte local ignorado: artifacts/evaluation/groq-eval-02.json.
SHA-256 del reporte: 2f0c6800cb83f6312a667586212f5b2c4369ed0f0a47c6139c8d06f2f3bef131.
El diagnóstico adicional permanece local en artifacts/evaluation/groq-eval-02-diagnostics.json; no se incorpora el cuerpo del proveedor al historial.

## Acumulado tras dos tandas

Dos casos reservados intentados una vez cada uno: un error terminal en extracción y un recorrido completo con siete coincidencias literales.
Solicitudes totales observadas: tres. Reintentos totales: cero. Quedan seis casos sin ejecutar.
Solo hay una muestra de checklist y una ejecución completa exitosa, además de la extracción fallida. No se estima precisión general ni se oculta el fallo inicial al resumir tiempos.
No se modificó el sistema a partir de estos resultados. Los 30 registros originales siguen sin ejecutarse.
