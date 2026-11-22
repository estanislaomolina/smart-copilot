# Mejora de fiabilidad — incident-v7

## Cambios generales

Groq conserva JSON estricto, citas exactas y el presupuesto configurado de cero o un reintento.
Un observador opcional registra cada intento: esquema, número, duración, estado HTTP, resultado y tipos de error con la raíz del campo. No registra claves, mensajes remotos, valores ni citas. No modifica la respuesta pública de la API.
Los tipos distinguen validación local, rechazo remoto de esquema, truncamiento, negativa del proveedor, herramientas inesperadas, cuota, timeout y transporte. Las citas ausentes y repetidas tienen códigos propios; siguen siendo rechazadas.
No se puede reconstruir retrospectivamente la causa de EVAL-01. EVAL-06 tenía cita inexistente y EVAL-08 rechazo remoto de esquema. No se inventa la propiedad exacta que Groq rechazó en este último.

La corrección sigue limitada a un intento adicional y comparte presupuesto con reintentos de transporte. Un HTTP 429 no se reintenta. Truncamientos, negativas y herramientas no se convierten en correcciones automáticas. Si el segundo intento falla, no se publican los datos inválidos.
La salida previa y errores locales usados para corregir permanecen como datos no confiables dentro de la conversación de corrección; nunca como instrucciones del sistema. No se hace fuzzy matching de citas. Una generación remota rechazada, si está disponible, se valida localmente solo para obtener códigos seguros; nunca se publica ni se introduce en el prompt.

## Ubicación sin tipo determinado

El prompt incident-v7 y las descripciones del esquema distinguen un nombre de lugar de su tipo.
Si el contexto no permite decidir si es calle, barrio o localidad, el nombre literal se conserva en reference con justificación y street/district quedan desconocidos.
La falta de altura no prueba que un nombre sea localidad. No hay listas de nombres ni expresiones regulares para memorizar calles.
Los contratos públicos no cambian y las decisiones humanas siguen teniendo precedencia. Este cambio guía al modelo; no es una garantía semántica ni una comprobación geográfica.

## Medición del corrector

El evaluador mantiene cero reintentos por defecto. --max-retries 1 habilita explícitamente el único intento adicional. --extract-only permite aislar extracción sin consumir la consulta del checklist.
Los reportes distinguen errores terminales de fallos intermedios recuperados. Conservan tiempos por etapa y diagnósticos de cada intento, sin datos de entrada. Un resultado final válido no borra el fallo anterior.
Los reportes de extracción sola no se mezclan con los del flujo completo. Tampoco se mezclan configuraciones de cero y un reintento.
Con un reintento, cada caso completo puede consumir hasta cuatro solicitudes, aunque el límite habitual sea dos sin reintentos.

Comparación propuesta de desarrollo, sin usar el conjunto nuevo:

~~~bash
python3 scripts/evaluate.py --provider groq --cases data/evaluation/reliability-development-v1.json --case DEV-RELIABILITY-06 --limit 1 --extract-only --max-retries 0 --output artifacts/evaluation/dev-retry-0.json
python3 scripts/evaluate.py --provider groq --cases data/evaluation/reliability-development-v1.json --case DEV-RELIABILITY-06 --limit 1 --extract-only --max-retries 1 --output artifacts/evaluation/dev-retry-1.json
~~~

Esperar entre ambas corridas para respetar el cupo. Son dos ejecuciones distintas, no un experimento controlado que aísle causalmente el efecto del reintento: incluso con temperatura cero las salidas pueden variar.
La recuperación se demuestra en una ejecución real solo si se observa fallo y posterior éxito dentro de esa misma etapa. Los transportes simulados permiten comprobar ese camino sin generar gasto.

## Separación de versiones

La primera corrida de ocho casos y su resumen quedan intactos.
Desde incident-v7, holdout-v1 se considera desarrollo porque sus resultados ya guiaron cambios. El registro splits.json explicita ese uso; las expectativas originales no se sobrescriben.
Dos casos de la primera corrida se copian como reliability-development-v1 para diagnosticar citas y formato.
holdout-v2 contiene dos casos nuevos, con expectativas previas y hash congelado antes de consultar proveedores. No deben usarse para modificar el prompt durante la corrida.
La muestra nueva es mínima y sintética; no demuestra generalización ni representatividad. El autor del conjunto y del cambio es el mismo agente, por lo que no se presenta como revisión humana independiente.
Los 30 registros del CSV original siguen fuera de estas pruebas.

## Verificación local

83 pruebas Python pasan. Los transportes controlados comprueban recuperación de un rechazo remoto y de una cita inválida, agotamiento del presupuesto, rechazo de truncamiento, ausencia de datos en los diagnósticos y conservación de la referencia ambigua.
El evaluador comprueba conteo de recuperaciones y omisión completa del checklist en extracción sola.
Estas pruebas técnicas no demuestran precisión del modelo real. Los resultados reales posteriores deben registrarse por separado sin borrar la línea base.

## Conservación de reportes

El comando rechaza un destino existente antes de construir el proveedor o enviar solicitudes. Para reemplazar un reporte debe elegirse explícitamente --overwrite; nunca puede sobrescribir sus propios casos de entrada ni fuentes de consolidación.
Este control se añadió después de una repetición accidental de una corrida de desarrollo durante una interrupción de ejecución. La incidencia debe figurar en los resultados y no atribuirse a un fallo del modelo ni ocultarse.

## Resultados reales

La comparación de desarrollo, la incidencia de ejecución y la primera corrida nueva están en [llm-reliability-results.md](llm-reliability-results.md).
Un caso nuevo completó seis comprobaciones y el otro falló aun con el reintento. No se afirma una mejora global ni se borra la línea base.
