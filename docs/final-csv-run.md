# Corrida final del CSV conocido

**Lectura actual:** consultar el [resultado registrado](#resultado-registrado-de-la-corrida-20bincident-v8).
Las secciones de lanzamiento y reanudación que siguen conservan el registro histórico.

scripts/evaluate_csv.py procesa los 30 registros originales, sin modificarlos, en orden y con el proveedor seleccionado.
Es una comprobación de desarrollo sobre datos ya inspeccionados; no evaluación independiente ni medición certificada de precisión.

## Ejecución

Con las dependencias instaladas y GROQ_API_KEY exportada:

~~~bash
python3 scripts/evaluate_csv.py --provider groq --interval 45 --max-retries 1 --output-dir artifacts/final-evaluation/una-corrida
~~~

La ejecución iniciada por el agente usa una copia congelada de ambos scripts y del CSV en un contenedor separado de la aplicación. Los archivos de entrada se montan solo para lectura, el directorio de resultados se monta aparte y no se publican puertos. No se utiliza la base de llamadas.
Docker Compose inyecta la credencial desde la configuración local; no se copia .env al directorio de ejecución ni a la imagen. No se imprime su contenido.
El nombre del contenedor, imagen, commit, argumentos sin secretos y rutas quedan en launch.json junto a input/ y output/. El contenedor permanece después de terminar para consultar su estado y logs.

## Controles

- 45 segundos mínimos entre solicitudes en la corrida iniciada; el comando exige al menos 30 en modo Groq.
- Un único reintento adicional por etapa, con el mismo presupuesto para corrección/transporte que el producto. Máximo 120 solicitudes para los 30 casos.
- HTTP 429 detiene la corrida. No se espera en bucle ni se reintenta automáticamente la cuota.
- Una sola ejecución puede escribir en la carpeta: bloqueo de proceso. Una carpeta existente requiere --resume explícito.
- Cada caso tiene un marcador durable antes de enviar solicitudes y un reporte escrito por reemplazo atómico al terminar.
- --resume conserva los casos ya registrados, incluidos fallos y errores de cuota. Un marcador sin reporte se registra como ejecución interrumpida, sin reenviar a ciegas.
- Se rechaza retomar con CSV, código, modelo o configuración distintos. No hay cambio automático a Mock.
- SIGTERM/SIGINT solicita detener la corrida. Para detener un contenedor usar docker stop -t 30 NOMBRE; si se fuerza su cierre, el marcador permite identificar el caso interrumpido.

## Referencias y mediciones

La extracción recibe solo transcripcion_cruda. El checklist recibe la conversación y las preguntas del protocolo realmente seleccionado; no se fuerza el subtipo o protocolo de la fila.
Categoría, subtipo, calle, altura e intersección se comparan literalmente con las anotaciones originales. No se normalizan enriquecimientos para forzar coincidencias.
Solo se incluyen expectativas de estado de preguntas mandatorias cuando su texto coincide con una etiqueta respondida o pendiente y no hay contradicción. No se infiere estado pendiente por mera ausencia ni se incorporan preguntas adicionales del CSV como protocolo.
La auditoría ya identificó enriquecimientos y ambigüedades en esas anotaciones. Una diferencia puede ser de formato, selección de protocolo, referencia incorrecta o interpretación; no se reporta automáticamente como error semántico.
Prioridad, riesgos y barrio/comuna quedan como referencias para revisión: prioridad es humana en modo LLM y barrio no equivale necesariamente a municipio.
Las entradas para revisión humana empiezan pendientes. No se usa otro LLM como juez.

Los tiempos por etapa incluyen la espera preventiva entre solicitudes. pacing_wait_seconds registra esa espera por extracción/checklist; al analizar latencia no se debe confundir con tiempo de inferencia. Las pausas no implican lentitud de la aplicación.
No se estima consumo ni costo.

## Archivos de salida

- manifest.json: proveedor, modelo, prompt, commit y hashes de CSV, suite y código.
- cases.json y references.json: expectativas derivadas y anotaciones para revisión, nunca enviadas al modelo.
- progress.json: estado, caso actual, cantidad procesada y conteos; se actualiza antes y después de cada caso.
- case-001.json a case-030.json: resultados, diferencias literales, evidencia y diagnósticos.
- summary.json: acumulado, resultados completos y métricas.

state=completed significa que se procesaron los 30, aunque existan diferencias o errores. stopped_rate_limit significa que se alcanzó cuota y quedaron casos sin intentar; no se presenta como corrida completa.
Al retomar, el error de cuota anterior se conserva. Si se decide repetir ese caso en otra corrida, debe identificarse por separado, sin borrar el primer resultado.
Los archivos de ejecución quedan ignorados en artifacts/. Tras finalizar se revisarán y se podrá versionar un resumen sin credenciales ni cuerpos remotos.

Verificación previa: tres pruebas del adaptador, persistencia de casos interrumpidos y control de ritmo/presupuesto; corrida completa y continuación con Mock sin red. La ejecución con Groq se revisará al terminar.

## Corrida iniciada

Se inició la corrida Groq el 2026-11-22 a las 02:16 UTC (21 de noviembre por la noche en Argentina), con el código congelado en 2fd69ee.
Contenedor: smart-copilot-csv-final-20261122-021650-947341.
Directorio local ignorado: artifacts/final-evaluation/20261122-021650-947341/.
El archivo artifacts/final-evaluation/latest.json permite ubicar la corrida.

Consultar avance:

~~~bash
docker logs -f smart-copilot-csv-final-20261122-021650-947341
~~~

El estado durable queda en output/progress.json y el acumulado en output/summary.json, dentro de ese directorio. Al terminar o detenerse, el contenedor queda disponible para inspeccionar su código de salida.
Se verificó al inicio que el contenedor estaba en ejecución y procesaba el primer caso. No se declara finalizada ni se revisan resultados anticipadamente; se hará cuando el propietario avise.

El contenedor de batch reutiliza la configuración del servicio api y hereda su healthcheck HTTP. Como ejecuta un script en vez del servidor web, Docker puede marcarlo unhealthy. El estado de esta tarea se consulta en progress.json, logs y código de salida del proceso; ese healthcheck no es el indicador del avance del batch. La aplicación principal sigue en su contenedor separado.

## Reanudación y nueva configuración

La reanudación 120B del 2026-11-22 03:12 UTC llegó al caso 5 y se detuvo nuevamente por cuota. quota-status.json registra TPD y retry-after=681; el resultado no se declara completo.
Se prepara una nueva corrida separada con openai/gpt-oss-20b e incident-v8. El runner nuevo puede usar un mínimo de 30 segundos entre solicitudes y extender esa espera según los encabezados TPM; el manifiesto registra la reserva de 6000 tokens. Ver [cambio y verificación](category-schema-v8.md).

## Nueva corrida con modelo disponible

La corrida 120B/incident-v7 quedó detenida con cinco registros por TPD. Sus resultados permanecen en el directorio anterior.
Se inició una corrida nueva con openai/gpt-oss-20b, incident-v8 y código congelado en 94f45ae:
- Contenedor: smart-copilot-csv-20b-20261122-032242-290108.
- Directorio local: artifacts/final-evaluation/20261122-032242-290108-20b-v8/.
- Intervalo mínimo: 30 segundos, ampliado cuando los encabezados indiquen menos de 6000 tokens disponibles.
- Un único reintento adicional por etapa. No se mezclan resultados con la corrida anterior.
- El healthcheck HTTP del servicio api está desactivado en el worker; el estado real queda en progress.json.
- La configuración local de la aplicación selecciona explícitamente el mismo modelo 20B.

Se verificó el primer caso completo: extracción válida tras corregir una señal y checklist válido. Su estado de comparación tiene diferencias respecto del CSV y no se convierte en una afirmación de precisión. Se mantiene pendiente completar y revisar los 30.
El acceso a 20B no elimina los límites gratuitos del proveedor. Un nuevo 429 se conserva y detiene la ejecución, sin bucles de solicitudes ni servicios pagos.

## Resultado registrado de la corrida 20B/incident-v8

Estado final observado: **detenida por cuota**, no completada.
Se registraron 29 de los 30 casos; el caso 030 quedó sin intentar.

- **21 casos** completaron extracción y checklist, con alguna diferencia literal respecto del CSV.
- **7 casos** terminaron con `invalid_provider_output`: seis en extracción y uno en checklist.
- **1 caso** terminó con `provider_rate_limited`, que detuvo la ejecución.
- **0 casos** coincidieron en todas las comprobaciones literales. No significa que todos sus campos fueran incorrectos.
- **69 solicitudes** en total, incluidos los reintentos. Once etapas terminaron válidas después de un reintento.

Hay **22 extracciones utilizables**: las 21 que completaron el flujo más la del caso cuyo checklist falló.
Sobre ellas, categoría coincidió literalmente en **16/22**, subtipo en **0/22** y los campos comparados de
ubicación en **30/66** (calle, altura e intersección; 22 × 3).
Solamente dos extracciones coincidieron en los tres componentes de ubicación a la vez.

Son denominadores de salidas disponibles, no tasas globales sobre los 30 registros.
Subtipo no es obligatorio en el producto y la referencia puede contener enriquecimientos;
un valor ausente o una diferencia de escritura cuenta como diferencia literal. Eso exige revisar los casos,
no cambiar el resultado automáticamente. Tampoco toda diferencia se puede atribuir al formato:
puede existir un error real de extracción.

Solo hubo **una comparación de estado de checklist** compatible con las preguntas del protocolo seleccionado,
y no coincidió. Las guías generales no reproducen todas las preguntas específicas del CSV.
Esta corrida no permite estimar precisión del checklist. Las **193 entradas de revisión humana** siguen
pendientes; no se afirma una tasa de afirmaciones correctas ni de alucinaciones.
Los tiempos incluyen pausas preventivas: no son latencia pura del modelo.

### Dónde leer y comprobar los números

El [resumen versionado](final-csv-results-v8.json) conserva configuración, conteos, métricas y el hash
del reporte original, sin transcripciones ni credenciales.

Los archivos locales originales están en
`artifacts/final-evaluation/20261122-032242-290108-20b-v8/output/`:

- `progress.json`: estado y conteos por caso.
- `summary.json`: acumulado, métricas y resultados detallados.
- `case-001.json` a `case-029.json`: comprobaciones y evidencia por registro.
- En cada comparación, `expected` es la anotación de referencia, `actual` lo extraído y `passed`
  indica igualdad literal; no es un veredicto semántico humano.

Estos resultados corresponden a **94f45ae / incident-v8 / openai/gpt-oss-20b**.
Los [cambios de cierre incident-v9](reliability-closure.md) se verificaron sin red y no tienen aún una nueva
corrida semántica con Groq. Se conservan ambos estados por separado, sin presentar mejoras no medidas.
