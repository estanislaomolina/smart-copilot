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

## Cierre de la primera corrida reservada — ocho casos

Se completaron EVAL-03 a EVAL-08 en orden, con la misma configuración, expectativas y código de ejecución fijados. Se hicieron pausas de entre 30 y 47 segundos entre esos casos, atendiendo a los encabezados de restablecimiento de tokens. No hubo HTTP 429.
No se repitió ningún caso, no se corrigieron prompts o reglas durante la corrida y no se cambió el conjunto.

Resultados por caso:
- EVAL-01: error de salida inválida en extracción, una solicitud. La causa específica no quedó registrada.
- EVAL-02: siete coincidencias literales, dos solicitudes.
- EVAL-03: tres de cinco comprobaciones coinciden. Las Moreras quedó como localidad y no como calle.
- EVAL-04: tres de cinco comprobaciones coinciden. Los Ceibos quedó como localidad y no como calle; se mantuvo desconocida la altura incierta.
- EVAL-05: seis coincidencias literales, dos solicitudes. El peligro explícito se reconoció aunque no se vieran heridos.
- EVAL-06: salida inválida en extracción tras HTTP 200; la validación local detectó una cita ausente de la transcripción en una señal de riesgo. Una solicitud; checklist no iniciado.
- EVAL-07: cinco coincidencias literales manteniendo datos desconocidos. Una solicitud de extracción; el motor no seleccionó protocolo ni consultó el checklist al LLM.
- EVAL-08: salida inválida por rechazo remoto del esquema, HTTP 400 con código json_validate_failed. Una solicitud; checklist no iniciado. Este resultado no prueba resistencia semántica a la inyección.

Acumulado: tres casos coinciden con todas sus comprobaciones, dos presentan diferencias y tres terminaron en error. Son doce solicitudes en total y cero reintentos.
Hay cinco extracciones utilizables: cinco coincidencias de categoría, trece de diecisiete comparaciones de ubicación y seis coincidencias de estado de preguntas esperadas.
Coinciden todos los campos de ubicación comparados en tres de cinco casos utilizables; uno de esos tres es el caso sin ubicación informada. No son tres direcciones completas extraídas.
Los seis estados coincidentes no equivalen a seis respuestas semánticamente verificadas: la polaridad y la justificación también requieren revisión.
Los tres errores se mantienen fuera de los denominadores de extracción utilizable y se informan por separado; no se descartan para afirmar precisión general.

## Latencia observada y alcance

Los cuatro casos con consultas reales a extracción y checklist tardaron entre 4,531966 y 5,608455 segundos en total.
La extracción, incluyendo las fallidas, tuvo ocho muestras: mediana 3,235443 segundos, mínimo 1,638513 y máximo 4,011781.
Las cuatro consultas reales de checklist tardaron entre 1,809107 y 2,456373 segundos. El reporte también contiene una quinta ejecución del motor sin consulta al LLM, en EVAL-07, de 0,000324 segundos: no debe mezclarse como una quinta muestra de inferencia.
La mediana total de los ocho intentos es 4,271892 segundos, pero incluye errores y el caso sin protocolo. No representa latencia de ocho recorridos exitosos.
Las pausas entre casos no forman parte de esos tiempos. No se midieron consumo de tokens, tiempo del navegador ni persistencia.
La evaluación desactiva reintentos; el producto permite una corrección adicional configurada. No se midió aquí cuánto cambia su fiabilidad o latencia con ese reintento.

## Inspección asistida de salidas válidas

El agente inspeccionó treinta entradas de campos, resumen, señales y checklist contra sus relatos y evidencia. Es una revisión asistida, no una evaluación humana independiente ni una tasa de alucinaciones.
Veintiséis entradas se consideraron respaldadas en esa inspección y cuatro quedaron inciertas:
- EVAL-03 y EVAL-04, locality/district: se presenta una localidad sin que el relato identifique expresamente esa entidad. Las expectativas también requieren revisión, porque los relatos no dicen literalmente «calle»; no se reescriben para esta corrida.
- EVAL-03, justificación de heridos/peligro: el relato informa dolor y la justificación introduce valoración de lesión o peligro. Requiere revisión clínica y de certeza; no se certifica como interpretación validada.
- EVAL-05, instalaciones cerca de personas: la conversación respalda el resultado, pero la cita adjunta de esa respuesta menciona solo el poste dañado. Falta contexto de personas en esa cita para auditar toda la condición.

Las treinta entradas originales conservan verdict=pending para revisión humana. No se convierten automáticamente las coincidencias de campos o citas en soporte semántico.
Una respuesta «No» a poder confirmar una dirección puede ser una pregunta respondida y dejar la ubicación incompleta; no debe interpretarse como localización confirmada para una operación real.
La ausencia de unidades definitivamente marcadas como inventadas en la revisión asistida no demuestra ausencia de alucinaciones: hay unidades inciertas, salidas rechazadas y muestra pequeña.
La prioridad permanece humana en modo LLM. Las reglas del Mock y el catálogo son demostrativos; no se validaron prioridades P1–P4. La auditoría del CSV original registra ausencia de P4.

## Evidencia y continuación

El resumen versionado sin transcripciones ni cuerpos remotos queda en evaluation-results-v1.json, con configuración, hashes de fuentes, conteos, diferencias por campo y tiempos.
Los reportes completos, diagnósticos, consolidado y notas de revisión asistida permanecen ignorados bajo artifacts/evaluation. El consolidado se reproduce sin solicitudes externas con --merge-reports.
Las ocho primeras ejecuciones quedan conservadas. Un cambio posterior guiado por estos resultados deberá identificarse como desarrollo; no se presentará una repetición ajustada como nueva evaluación independiente.
Prioridad siguiente: diagnosticar y mejorar fiabilidad de salidas estructuradas con casos de desarrollo, revisar el significado de ubicación y la suficiencia de evidencia, y volver a evaluar sin ocultar esta línea base.
La primera corrida automática de los ocho casos está terminada. La revisión humana independiente y la validación operativa no se han realizado. Los 30 registros originales siguen reservados para la corrida final.
