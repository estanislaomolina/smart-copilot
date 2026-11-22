# Corrida final del CSV conocido

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
