# Evaluación: separación, mediciones y revisión humana

## Alcance y conjuntos

- data/raw/dataset_challenge_soflex.csv: 30 casos originales ya conocidos durante desarrollo. Se conservan intactos y su corrida queda para el final; no sirven como evaluación independiente.
- data/evaluation/development.json: dos casos conocidos utilizados para comprobar el comando y analizar fallos.
- data/evaluation/holdout-v1.json: ocho relatos sintéticos propios con expectativas definidas antes de ejecutar proveedores. Su hash queda en holdout-v1.sha256. Se prepararon sin ejecutar ni usarse para modificar prompts o reglas. Posteriormente se ejecutó la primera corrida completa, sin repeticiones: tres casos coinciden con las comprobaciones, dos tienen diferencias y tres fallaron en extracción. No se usaron los resultados para ajustar esta versión. Ver [resultados](evaluation-results.md).
- data/synthetic/development.json: ocho especificaciones previas apartadas; no se incorporaron automáticamente a esta evaluación.

Los casos reservados cubren las seis categorías, presencia frente a atrapamiento, respuestas descriptivas, negativas, altura ausente o incierta, corrección completa de dirección, información insuficiente e instrucciones no confiables dentro del relato. Las preguntas esperadas existen en el catálogo general. Las notas por caso orientan la revisión, sin llegar al proveedor.

Es una muestra pequeña y sintética creada en el mismo proyecto; no demuestra representatividad ni independencia entre autores. Las expectativas siguen siendo susceptibles de error y requieren revisión humana. Los relatos no son escenarios operativos validados.

Antes de usar el conjunto reservado, fijar el commit/configuración y comprobar su hash desde la raíz:

~~~bash
sha256sum -c data/evaluation/holdout-v1.sha256
~~~

Si sus resultados se utilizan para cambiar prompts o reglas, esos casos pasan a desarrollo para esa nueva versión. No cambiar expectativas para conseguir coincidencias. Una expectativa incorrecta se corrige con justificación y nueva versión, conservando el resultado previo.

## Ejecución acotada

Para comprobar el evaluador con casos conocidos y sin red:

~~~bash
python3 scripts/evaluate.py --provider mock --output artifacts/evaluation/development-stages.json
~~~

Máximo dos casos por defecto. --case selecciona un ID y se puede repetir; --limit establece el máximo explícito. El reporte distingue casos no seleccionados de los omitidos por un 429.

Ejemplo para una futura consulta real de un caso reservado, cuando se decida iniciar la evaluación:

~~~bash
python3 scripts/evaluate.py --provider groq --cases data/evaluation/holdout-v1.json --case EVAL-01 --limit 1 --output artifacts/evaluation/groq-eval-01.json
~~~

GROQ_API_KEY debe estar exportada en el entorno; el comando no carga .env. La primera tanda se ejecutó con esta selección dentro del contenedor y se registró por separado. Solo se envían transcripción y preguntas del protocolo seleccionado: nunca expectativas, IDs de casos ni notas de revisión. La selección del protocolo mantiene el comportamiento del producto, sin forzar la categoría esperada. Si faltan preguntas esperadas, revisar también el protocolo seleccionado antes de atribuir el fallo al intérprete del checklist.

La evaluación desactiva por defecto los reintentos de Groq, aunque el entorno del producto configure uno. --max-retries 1 habilita un único intento adicional por etapa y puede elevar el máximo de dos a cuatro solicitudes por caso. Cada caso hace como máximo una extracción y una consulta de checklist; si no se selecciona un protocolo, no hay segunda consulta. El máximo por defecto es cuatro solicitudes. Un 429 interrumpe la corrida y omite el resto. No hay sustitución automática por Mock. Esperar y decidir una nueva tanda fuera del comando, sin bucles de reintentos.

No se modificó la política de reintentos de la aplicación.

## Qué mide el reporte v2

- Comparaciones literales por campo, estado del checklist y texto de respuesta cuando se especificó. Solo las respuestas ignoran mayúsculas y espacios exteriores; no se equiparan paráfrasis.
- Casos con campos de ubicación comparados y cuántos coinciden en todos esos campos. Si falla la extracción, no entra en ese denominador; el error se informa aparte.
- Errores por etapa/código y cantidad de salidas inválidas terminales. Los reportes nuevos incluyen diagnósticos de intentos intermedios del adaptador Groq y recuperaciones; los reportes históricos sin esos eventos no permiten reconstruirlos. Los reintentos están desactivados por defecto.
- Tiempo de extracción, checklist y total por caso, con mínimo, mediana, máximo y número de muestras. Incluye trabajo local de cada etapa y espera por el transporte; no es latencia aislada del modelo ni tiempo percibido en el navegador. Las etapas fallidas también se miden y las no iniciadas quedan null. El total abarca el análisis de un caso, sin carga de archivos, creación del cliente, escritura del reporte, persistencia ni comunicación navegador–API.
- Solicitudes de transporte observadas por etapa y reintentos derivados de esas cuentas. Mock registra cero; un proveedor sin contador registra null. No se inventan intentos ni consumo.
- Proveedor, modelo, configuración, prompt, hash del conjunto e IDs seleccionados.

Si falla el checklist, se conservan las comparaciones y entradas revisables de la extracción ya obtenida. No se evalúan como incorrectas preguntas que no llegaron a procesarse. El consumo sigue sin estar disponible en el contrato y se registra como null.

Una diferencia literal no demuestra una interpretación incorrecta. Una coincidencia tampoco prueba soporte semántico. No hay juez LLM, porcentaje de precisión general ni política validada de prioridades P1–P4. En modo LLM la prioridad sigue siendo humana; el Mock conserva sus reglas demostrativas.

## Revisión de afirmaciones

El reporte genera human_review.entries para cada campo conocido, resumen, señal y respuesta no pendiente, conservando origen, justificación y evidencia. No incorpora la transcripción completa: se consulta el caso original por ID. Cada entrada empieza con verdict=pending. Las entradas pueden contener varias afirmaciones y no equivalen a hechos atómicos independientes.

Guardar una copia del reporte dentro de artifacts para la revisión y mantener el original. Para cada entrada, leer toda la conversación y las correcciones, además de las citas:

1. supported: significado, polaridad, alcance y certeza están respaldados. Una inferencia debe estar identificada como tal y no presentarse como hecho confirmado.
2. unsupported: hay una afirmación inventada, una negación invertida, una dirección descartada presentada como vigente o una conclusión más fuerte que el respaldo. Explicar en reviewer_notes.
3. uncertain: no se puede adjudicar con seguridad si la interpretación está respaldada; explicar el motivo. No equivale a supported.
4. pending: todavía no revisada. Que una cita exista o coincidan los valores esperados no cambia este estado automáticamente.

Por ejemplo, una cita sobre alguien dentro no sustenta por sí sola que esté atrapado. Las preguntas compuestas requieren revisar todas sus condiciones. Las instrucciones provienen del catálogo demostrativo y no se convierten en recomendaciones validadas al pasar esta revisión.

Contar veredictos después de revisar una copia, sin llamar proveedores:

~~~bash
python3 scripts/evaluate.py --summarize-review artifacts/evaluation/reviewed.json
~~~

Este comando cuenta los veredictos actuales de las entradas, sin modificar el resumen automático inicial ni los resultados literales. No calcula una tasa de alucinaciones: reporta entradas revisadas, pendientes, sin respaldo e inciertas con su denominador visible.

## Comprobación de este incremento

Se ejecutaron únicamente los dos casos conocidos con Mock, además de una selección individual del mismo conjunto. Ambos casos completos conservaron diferencias; no se ampliaron reglas ni se cambiaron sus expectativas.
Se verificaron tiempos y conteos con un reloj y transporte simulados, preservación parcial ante fallo del checklist y ausencia de certificación semántica automática.
Los ocho casos reservados se validaron estructuralmente y contra las preguntas del catálogo, sin ejecutar sus transcripciones con ningún proveedor.
No se hicieron consultas a Groq, no se ejecutó el CSV original y no se midió latencia real del LLM en este incremento.

## Primera tanda posterior

Se ejecutó EVAL-01 con Groq, una solicitud y cero reintentos. Falló la extracción por salida inválida y no se inició el checklist. Los siete casos restantes no se seleccionaron. No se cambió el sistema ni las expectativas ni se repitió el caso. Ver [configuración, tiempos y limitaciones](evaluation-results.md).

## Segunda tanda posterior

Se ejecutó EVAL-02 con Groq: dos solicitudes, cero reintentos, siete coincidencias literales y unos cinco segundos en total. Las entradas conservan su estado pendiente de revisión humana. No se repitió el caso fallido ni se cambiaron prompts, reglas o expectativas. Ver [resultados acumulados](evaluation-results.md).

## Consolidar tandas sin repetir consultas

El comando --merge-reports permite consolidar reportes v2 con el mismo conjunto, proveedor, modelo, prompt y configuración:

~~~bash
python3 scripts/evaluate.py --merge-reports artifacts/evaluation/groq-eval-[0-9][0-9].json --output artifacts/evaluation/groq-holdout-summary.json
~~~

Seleccionar solo los reportes de resultados, sin archivos de diagnóstico ni copias revisadas del mismo caso. El comando conserva fallos previos y los tiempos de etapas no iniciadas quedan null. Rechaza reportes duplicados, IDs repetidos o configuraciones distintas; las ejecuciones repetidas deben compararse por separado, sin reemplazar la primera.
Cada fuente se identifica por nombre y hash. No se consultan proveedores ni se incluyen claves o cuerpos remotos. El código de salida sigue siendo 1 si hay diferencias, errores u omisiones.

## Corrida completa posterior

Se completaron los ocho casos con doce solicitudes, sin reintentos y con pausas; no hubo respuestas 429. Se conservan tres errores, dos casos con diferencias y tres casos coincidentes con las comprobaciones.
La inspección asistida del agente abarcó las treinta entradas utilizables: veintiséis consideradas respaldadas y cuatro inciertas. La revisión humana sigue pendiente y no se afirma una tasa de alucinaciones ni precisión general.
Ver [resultados, límites y siguientes decisiones](evaluation-results.md) y [resumen versionado](evaluation-results-v1.json). Los prompts, las reglas, el catálogo y las expectativas quedaron sin cambios durante esta corrida.

## incident-v7 y nuevo conjunto reservado

Los ocho casos de la línea base pasan a desarrollo para cambios posteriores, según splits.json. No se borran sus resultados ni se reescriben sus expectativas.
holdout-v2 contiene dos casos nuevos congelados antes de ejecutar proveedores. Ver [diagnóstico, política de ubicación y medición de correcciones](llm-reliability.md).
--extract-only limita la medición a extracción. --max-retries 1 mide el presupuesto del producto; la configuración y el modo quedan registrados y no se consolidan con corridas distintas.

Los reportes existentes no se reemplazan por defecto: elegir una ruta nueva o --overwrite explícito. El rechazo ocurre antes de consultar al proveedor. Los casos de entrada y las fuentes de una consolidación nunca pueden ser el destino, incluso con esa opción.
