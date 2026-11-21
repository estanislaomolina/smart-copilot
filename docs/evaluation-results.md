# Resultados de evaluación — primera tanda

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
