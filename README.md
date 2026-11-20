# Smart Copilot

Prototipo de asistencia para operadores de emergencias a partir de transcripciones de texto.

## Estado

Mock de demostración con extracción parcial, riesgos/prioridad y motor de protocolos separados. Hay panel para analizar texto, inspeccionar evidencia, corregir categoría/prioridad y seleccionar protocolos. La conversación admite nuevos turnos y actualización del análisis conservando decisiones manuales. La guía muestra instrucciones, próxima pregunta y checklist editable. La Carta de Llamada ya se guarda en SQLite, se recupera al recargar, admite revisión explícita y derivación simulada. Categoría, prioridad y cada campo de ubicación tienen revisión individual. La integración LLM con Haiku se hará después de completar ese flujo.

## Objetivo

El operador carga una transcripción, revisa ubicación, tipología y prioridad sugerida, completa el checklist y consulta instrucciones de prearribo. Puede corregir los datos y derivar una Carta de Llamada estructurada. El despachador decide los recursos; el copiloto no los despacha.

## Roadmap y forma de trabajo

Ver [ROADMAP.md](ROADMAP.md) para hitos, criterios de aceptación y flujo de ramas y pull requests.

## Ejecutar el panel y la API

Requiere Docker con Compose:

```bash
docker compose up --build
```

El panel queda accesible en [localhost:8000](http://localhost:8000), con [salud](http://localhost:8000/health), [documentación HTTP](http://localhost:8000/docs) y [contratos JSON Schema](http://localhost:8000/contracts). El endpoint `POST /api/analyze` procesa transcripciones mediante reglas de demostración. El catálogo y checklist se aplican por separado. El panel consume ambos endpoints sin enviar transcripciones a terceros.

No requiere claves ni un archivo de configuración. `.env.example` permite configurar `APP_PORT` y documenta `LLM_PROVIDER=mock`, único proveedor implementado por ahora. El primer build descarga la imagen y dependencias; el servicio en ejecución no necesita servicios externos.

Para detenerlo: `docker compose down`. El volumen `call-data` conserva las llamadas al recrear el contenedor. `docker compose down -v` elimina ese volumen y sus datos; no usarlo si se quiere conservar la atención. Los contratos, decisiones y verificaciones están en [domain-contracts.md](docs/domain-contracts.md).

## Primer recorrido del operador

1. Pegar una transcripción y presionar **Enter** para analizar. **Shift+Enter** agrega una línea. También se puede usar **Analizar llamada**.
2. En **Revisar datos**, los valores muestran su estado (sugerido, revisado o sin información). **Editar** abre el control de categoría, prioridad o ubicación: **Confirmar** acepta el valor existente, **Guardar** aplica una corrección y **Cancelar** descarta la edición. La revisión individual es opcional; no es necesario confirmar todos los campos para continuar. Guardar un valor vacío lo deja sin información y conserva esa decisión al actualizar el análisis.
3. En **Guiar la llamada**, la categoría conocida activa automáticamente una guía general. No hace falta elegir subtipo para comenzar; **Elegir subtipo (opcional)** permite cambiar a una guía específica. La guía muestra: instrucciones del catálogo con advertencia de demostración, próxima pregunta y checklist completo. **Usar esta pregunta** copia su texto al campo Operador y enfoca la respuesta del ciudadano. La guía, el campo preparado y el checklist muestran el mismo número de pregunta. Si se incorpora primero el turno del operador, queda esperando la respuesta del ciudadano; al agregarla se muestra el estado devuelto por el backend y su evidencia. Preparar o preguntar no marca el ítem como respondido. Editar libremente la pregunta o cambiar de guía quita la asociación preparada; la revisión manual conserva su precedencia. La guía destaca **DECIR AHORA** y **PREGUNTAR DESPUÉS**. Se prioriza una pregunta ambigua con aclaración del catálogo, después otras ambiguas y luego pendientes; dentro de cada grupo se conserva el orden del catálogo. Es un orden de asistencia de demostración, no una política clínica de prioridades. No se selecciona un protocolo por defecto cuando hay varios candidatos.
4. En **Continuar conversación**, agregar lo dicho por el operador y/o el ciudadano y pulsar **Agregar y actualizar análisis** (Enter desde la respuesta; Shift+Enter agrega una línea). Se analiza el historial completo y se actualiza el checklist.
5. **Revisar Carta de Llamada** muestra categoría, prioridad, ubicación, protocolo, señales con procedencia, preguntas pendientes y evidencia. Permite redactar el resumen y las observaciones del operador.
6. **Guardar borrador** guarda el estado actual. Para **Confirmar revisión**, marcar la declaración de revisión; los turnos sin incorporar deben enviarse o vaciarse primero. Después se habilita **Derivar · Simulación**, que registra fecha e identificador `SIM-CAD-…` sin contactar un CAD real.
7. **Nueva llamada** guarda primero la actual y luego limpia el espacio. Si el guardado falla, no abandona la llamada. **Volver a la llamada anterior** y **Recuperar llamada** permiten reabrir las llamadas persistidas.

En escritorio, transcripción, datos y guía se muestran en tres columnas dentro de la altura disponible. Los paneles de datos y guía permiten desplazamiento propio cuando el contenido lo requiere; evidencia, fuentes y explicaciones se despliegan a demanda. En pantallas angostas los bloques se reorganizan para mantener el texto legible.

El historial existente queda fijo para conservar los offsets de evidencia. Los nuevos turnos se anexan al final: es una simulación de transcripción progresiva, no una propuesta para que un operador real transcriba mientras atiende. No hay acción de reanálisis sobre el mismo texto. Cambiar categoría o tipo de incidente actualiza las preguntas sin volver a ejecutar el extractor.

Al añadir turnos se conserva categoría, prioridad y ubicación revisadas, incluso si el operador decidió dejarlas sin determinar. La combinación también preserva campos con procedencia de operador y respuestas manuales compatibles. Si una sugerencia nueva difiere de una decisión humana se muestra un aviso; no la sobrescribe. El protocolo elegido explícitamente se mantiene cuando corresponde a la categoría; la guía general automática se vuelve a decidir por la categoría actual; si deja de corresponder se solicita elegir otro. La extracción y el cálculo del protocolo deben terminar correctamente antes de reemplazar el estado visible. Si falla alguno, se conservan el historial anterior, sus correcciones y los turnos sin enviar para reintentar. El límite es de 50.000 caracteres para la conversación completa.

La comprensión del mock sigue siendo conservadora: anexar una respuesta no garantiza que una paráfrasis se interprete correctamente. Un evaluador contextual separado reconoce diálogo explícito y un repertorio limitado sobre personas atrapadas; una señal de presencia dentro solo aporta evidencia ambigua, nunca confirma atrapamiento. Las otras preguntas conservan la interpretación de diálogo explícito; no se añadieron reglas por registro para este incremento. El estado se guarda localmente en SQLite; la derivación es una simulación explícita. El mock puede omitir señales de gravedad y subestimar la prioridad; sus valores siempre requieren revisión humana.

El caso del incendio con una persona dentro queda ambiguo con cita verificable. La guía propone una aclaración registrada en `data/protocols/follow-ups.json` (`demo-follow-ups-v1`), con procedencia propia y advertencia de demostración; no procede del CSV. El archivo original y el catálogo generado se mantienen intactos. El motor selecciona protocolos y combina revisiones manuales; `ChecklistEvaluator` recibe solamente conversación y preguntas del protocolo, y su salida se valida contra IDs, textos, aclaraciones autorizadas y offsets. `MockChecklistEvaluator` es la única implementación actual. Haiku sigue pendiente: no hay evaluación semántica general ni llamadas externas.

Los tres elementos de incertidumbre —resumen central, próxima pregunta y checklist— se calculan desde la misma lista de preguntas publicada por el protocolo. La actualización de seguimiento guarda la referencia al ítem, no otra copia de su estado o respuesta. La respuesta y evidencia del backend se mantienen en ese ítem; el historial conserva el relato anterior. Los borradores de edición manual solo afectan la vista publicada al guardarse. La sincronización no amplía la comprensión semántica del mock: una respuesta no interpretable sigue ambigua para revisión.

La prioridad muestra explícitamente **Prioridad sugerida: P1** o **Prioridad confirmada por el operador: P1**, según su procedencia humana. Confirmar cambia la procedencia, no convierte las reglas del mock en protocolos validados. La tipografía y los espacios se compactaron para reducir desplazamiento; las aclaraciones centrales usan la pregunta breve del checklist y la guía conserva el texto completo.

El bloque **DECIR AHORA** se destaca en rojo y negrita como acción de comunicación, no como indicador de una nueva gravedad. El panel central separa **Información reportada**, **Por aclarar** y **Riesgos potenciales**. La señal existente de presencia de personas usa procedencia `transcript` y etiqueta de reporte; no confirma atrapamiento ni capacidad de salir, y no equivale a verificación independiente. Los patrones de detección y las reglas de prioridad se mantienen. La prioridad sugerida y la certeza de cada dato se muestran por separado.

Cada pregunta tiene un selector de estado y una acción **Revisar**. Marcarla respondida requiere una respuesta; pendiente por decisión manual, ambigua y no aplicable requieren una justificación. **Guardar revisión** valida el cambio en el backend y conserva la procedencia humana. Si el diálogo posterior aporta una respuesta distinta o incierta, se muestra un aviso sin reemplazar lo registrado por el operador. La comparación inicial es conservadora sobre texto/estado; no demuestra equivalencia o contradicción semántica. Las preguntas e instrucciones siempre provienen del protocolo aplicado. No se agregan preguntas en el frontend. La confirmación aparece dentro de la edición, sin botones permanentes junto a cada sugerencia. La revisión final sigue disponible desde la Carta. La confirmación es individual: aceptar la categoría no confirma la prioridad ni cambia el protocolo o las respuestas revisadas. Solo cambiar la categoría vuelve a calcular la guía.

Para desarrollar el panel: Node 24 y `cd frontend && npm ci && npm run dev`, con la API en el puerto 8000 (`uvicorn backend.main:app --reload`). Vite usa un proxy local para `/api`. `cd frontend && npm run build` verifica TypeScript y genera el build; FastAPI sirve ese build en Docker, sin proceso Node durante la ejecución. React/React DOM implementan la interfaz; TypeScript valida tipos y Vite compila los assets. Las versiones resueltas están en el lockfile.

## Carta de Llamada y persistencia

La interfaz guarda automáticamente tras 700 ms sin cambios, cuando no está analizando. La franja superior distingue **Cambios sin guardar**, **Guardando** y **Guardada en SQLite**. Recargar antes de que termine una escritura puede perder los últimos cambios; el botón de guardado permite comprobar su resultado. No se promete guardado mientras la API está caída.

Se conserva la transcripción completa, extracción original, datos revisados, evidencia, confirmaciones manuales, protocolo y checklist, resumen, notas y turnos todavía sin incorporar. Cada modificación efectiva genera una versión completa; un guardado idéntico no genera otra versión. El historial visible muestra eventos y fechas; las instantáneas anteriores quedan en SQLite, sin una interfaz para restaurar versiones antiguas.

La revisión corresponde a una versión de la carta, **no confirma automáticamente cada campo**. Las sugerencias y los datos desconocidos conservan su procedencia. En esta demostración se permite revisar con preguntas pendientes, visibles en la ficha; todavía no existe una política operativa validada de campos obligatorios. Cualquier modificación persistida posterior, incluidos turnos en preparación, devuelve la carta a borrador y exige revisar nuevamente antes de derivar. Los comprobantes anteriores se conservan en el historial. Reintentar una derivación de la misma revisión devuelve el mismo comprobante.

SQLite usa control de versión para evitar sobrescribir cambios desde otra pestaña. Si otra escritura se adelantó, se informa el conflicto y se permite **Descartar cambios locales y recuperar guardado**, de forma explícita. No se combinan silenciosamente dos ediciones concurrentes.

API:

- `GET /api/calls`: últimas 50 llamadas, ordenadas por actualización.
- `GET /api/calls/{uuid}`: carta y estado de atención completo.
- `PUT /api/calls/{uuid}`: `{expected_revision, snapshot}`; usar revisión 0 al crear.
- `GET /api/calls/{uuid}/revisions`: últimos 100 eventos y versiones.
- `POST /api/calls/{uuid}/review` y `/refer`: `{expected_revision, acknowledged: true}`.

El servidor controla estados, fechas e identificadores. Valida evidencia y referencias del checklist, y toma las instrucciones del catálogo en lugar de confiar en las enviadas por el cliente. Los modelos completos están en `/docs`.

Sin Docker, `CALLS_DB_PATH` permite cambiar la ruta predeterminada `data/private/calls.sqlite3`. En Compose se utiliza `/app/data/private/calls.sqlite3` dentro del volumen. No se guarda la base en Git ni se incorpora a la imagen. El navegador conserva solamente el UUID de la llamada activa en `localStorage`; los datos están en el servidor local. Es un prototipo local sin autenticación ni política de retención para operación real.

## Analizar una transcripción

```bash
curl http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Llamante: En Av. Corrientes 1540 hay fuego."}'
```

La respuesta incluye datos, evidencia y advertencias. Los campos que las reglas no pueden resolver quedan desconocidos. El mock mantiene cobertura parcial de ubicación, categoría, riesgos y prioridad, sin buscar reproducir todas las etiquetas del CSV. Ver [reglas de simulación](docs/mock-priority-risks.md). Las preguntas e instrucciones provienen del motor de protocolos separado.

## Catálogo y checklist

- `GET /api/protocols?category=INCENDIO_RESCATE` lista candidatos.
- `POST /api/protocols/apply` recibe `request`, `data` y un `protocol_id` opcional.
- La categoría conocida activa su guía general (`selection=general`, `selection_origin=category`); `scope` distingue guía general y protocolo específico. Sin categoría no se elige una guía por defecto. No se copian respuestas del CSV.
- El checklist conserva evidencia y revisión manual compatible. La interpretación inicial se limita a diálogo explícito; respuestas implícitas en relato libre quedan pendientes.
- Las instrucciones del catálogo conservan fuente y estado `demo_unverified`.

Las seis guías generales están definidas explícitamente en `data/protocols/general.json`, versión `general-demo-v1`. Son curaduría propia de demostración, separada de los 30 protocolos derivados del CSV; no se generan fusionando sus instrucciones ni reconociendo establecimientos concretos. Se reutilizan formulaciones e IDs de preguntas compatibles para conservar revisiones al cambiar de guía; no se importan respuestas ni estados del CSV. Su contenido requiere revisión antes de cualquier uso operativo. Cubrir las seis categorías no implica comprender todos sus incidentes ni validar las instrucciones.

Ver [API, ejemplos y límites](docs/protocol-engine.md). Para regenerar el catálogo: `python3 scripts/build_protocol_catalog.py`.

## Pruebas del mock y la API

En un entorno virtual de Python 3.12:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

Verificación del primer panel: build de TypeScript/Vite, 43 tests del backend y arranque saludable con Docker Compose. Se comprobó en Chromium el análisis, la selección de protocolo, la carga con Enter y el salto de línea con Shift+Enter, la recuperación de la llamada anterior con sus correcciones, el cambio de categoría, la vista móvil y la conservación de datos frente a una petición fallida. No equivale a validación operativa ni evaluación independiente.

Verificación del incremento de conversación: 45 tests del backend, tres pruebas de anexado y conservación de decisiones en el frontend (`cd frontend && npm test`, con el runner incluido en Node 24), y build de TypeScript/Vite. Se comprobó en Chromium la actualización repetida, el checklist, la conservación de decisiones y protocolo, el aviso de discrepancias y la recuperación ante fallo de la API de protocolos sin duplicar turnos al reintentar, en escritorio y móvil. Se corrigió la segmentación de relatos iniciales sin etiquetas al anexar turnos y se acepta `Ciudadano:` como alias de `Llamante:`, sin reescribir el texto ni sus offsets.

Verificación de la guía editable: build y tres pruebas del frontend, 47 tests del backend. En Chromium se comprobaron el orden instrucciones/pregunta/checklist, uso de la pregunta, avance tras la respuesta, los cuatro estados manuales, conservación de revisiones y avisos ante discrepancias, fallo de guardado con reintento y presentación en escritorio/móvil.

Verificación contextual y de guía visual: 50 tests del backend, cuatro pruebas del frontend y build. Incluye regresión del incendio, afirmación/negación espontánea, incertidumbre, contradicciones y correcciones, aclaración posterior, preservación manual y rechazo de evidencia inválida del evaluador. Se verificó Docker Compose y en Chromium el ciclo evidencia → aclaración versionada → respuesta negativa → siguiente pregunta. La selección de la próxima pregunta también se comprobó con estados genéricos y con una respuesta incierta sobre gas, sin añadir reglas al extractor. Estas comprobaciones son de desarrollo, no una evaluación semántica independiente.

Verificación de guías generales: 51 tests del backend, cuatro del frontend y build. Se comprobó una guía por cada categoría, ausencia de elección arbitraria cuando la categoría es desconocida y, en Docker/Chromium, asistencia automática, actualización progresiva, confirmaciones conservadas y cambio opcional de guía. La corrida global de los 30 registros se hará al completar el flujo y quedará reportada como verificación sobre casos conocidos.

Verificación de seguimiento y procedencia: se mantuvieron los 51 tests del backend y cuatro del frontend. Se comprobaron en Docker/Chromium el contraste rojo/negrita, vínculo por ID y número de pregunta, envío separado de pregunta y respuesta, evidencia en el ítem actualizado, recuperación de la llamada y eliminación de la asociación al editar libremente el texto. La procedencia de presencia se distingue del riesgo inferido; no se cambiaron patrones ni reglas de prioridad.

Verificación de Carta y SQLite: 56 tests del backend (cinco nuevos para persistencia y transiciones), cuatro del frontend y build. En Chromium se comprobaron guardado y recarga con prioridad manual y turnos sin incorporar, revisión explícita, derivación simulada, recuperación del comprobante, invalidación al editar, listado de llamadas y presentación móvil. Se verificó también la conservación de respuestas manuales del checklist y un conflicto de escritura: el borrador local sigue visible y la versión del servidor solo se recupera por acción explícita. La llamada sobrevivió a recrear el contenedor con su volumen. La imagen no incorpora la base de ejecución. Estas comprobaciones no evalúan la precisión semántica del mock ni reemplazan la corrida final pendiente.

Verificación de revisión individual: 56 tests del backend, cinco del frontend y build. Se cubren los cinco campos de ubicación y el vaciado explícito frente a una nueva extracción; SQLite conserva sus decisiones. En Chromium se comprobó que confirmar categoría no confirma prioridad ni borra la guía o respuestas manuales, y que las correcciones sobreviven a agregar turnos y recargar y se reflejan en la Carta. Se comprobó también la vista móvil. El ajuste de edición a demanda se comprobó con build, las cinco pruebas del frontend y Chromium: ausencia de confirmaciones permanentes, confirmar/guardar/cancelar dentro del editor, conservación al actualizar y recargar, Carta y vista móvil. La revisión final no exige confirmar campo por campo. No se ampliaron reglas de extracción ni se realizó la corrida final de los 30 registros.

Se comparan valores esperados revisados del CSV y variaciones de sus relatos. Son pruebas de desarrollo, no una evaluación independiente de generalización.

## Exploración de datos

Con Python 3.10 o superior, sin instalar dependencias:

```bash
python3 scripts/audit_dataset.py
python3 scripts/audit_dataset.py --json
```

Para recorrer la exploración visual, abrir [data_exploration.ipynb](notebooks/data_exploration.ipynb), seleccionar un kernel de Python y ejecutar las celdas en orden. Requiere un entorno de notebooks, como la extensión Jupyter de VS Code, y estas dependencias opcionales en el entorno del kernel:

```bash
python3 -m pip install -r notebooks/requirements-notebook.txt
```

El notebook solo importa y llama funciones de los scripts: auditoría en `scripts/audit_dataset.py` y presentación en `scripts/explore_dataset.py`. Incluye vista previa, resumen, dos gráficos y ejemplos de hallazgos.

Ver [hallazgos, uso de columnas y limitaciones](docs/data-audit.md). La auditoría es de solo lectura; las señales de coincidencia literal no equivalen a errores semánticos.

Los [ocho casos sintéticos de desarrollo](data/synthetic/development.json) quedan apartados por ahora. Primero se trabajará con el dataset provisto; después del primer extractor se decidirá qué casos adicionales hacen falta. No son un conjunto reservado ni resultados de evaluación de un modelo.

## Arquitectura propuesta

- Backend: Python, FastAPI y Pydantic.
- Panel: React y TypeScript.
- Persistencia: SQLite para cartas y revisiones.
- Proveedores: mock determinista y un proveedor LLM real.
- Protocolos: catálogo local versionado con procedencia y estado de revisión.
- Ejecución: Docker Compose, sin servicios externos necesarios durante el uso del modo mock.

Flujo: transcripción → extracción → validación → selección de protocolo → revisión humana → carta persistida. La derivación a CAD es simulada e identificada como tal.

Fine-tuning, múltiples agentes y bases vectoriales quedan fuera del alcance inicial.

## Datos y publicación

Se incluye `data/raw/dataset_challenge_soflex.csv`, provisto para el assessment y descrito en la consigna como sintético. Se conserva sin modificaciones y se atribuye a SOFLEX; no se le asigna una licencia propia ni se presenta como protocolo operativo validado. Se utilizará para ejemplos, catálogo de referencia y evaluación según las separaciones documentadas.

El PDF de la consigna se mantiene local, fuera de Git y de la imagen: no hace falta para ejecutar el prototipo. El repositorio permanece privado durante el desarrollo; se prevé hacerlo público al preparar la entrega.

- Se añadirán casos sintéticos propios para evaluar cambios y situaciones ausentes del dataset.
- Las claves se configurarán por variables de entorno; solo se versionará una plantilla sin secretos.
- El modo mock no enviará datos a terceros. Un proveedor remoto requerirá configuración explícita y será visible en el panel.
- Las trazas no almacenarán transcripciones completas por defecto.
- Antes de publicar se revisarán archivos, historial, capturas y video.

## Evaluación prevista

El dataset es pequeño y no cubre todas las prioridades. Algunas etiquetas agregan información ausente del relato y las listas de preguntas no siempre son complementarias. Se revisarán las referencias antes de usarlas como resultados esperados.

Se separarán ejemplos de desarrollo y casos reservados. Un caso usado en el prompt o disponible como referencia recuperable no se presentará como evaluación independiente.

Se reportarán exactitud de ubicación y categoría, confusiones de prioridad, preguntas marcadas como respondidas sin evidencia, afirmaciones sin respaldo, validez de salidas, errores, latencia y consumo. Se incluirán conteos y límites del tamaño de muestra.

## Criterios de aceptación

- Arranca con `docker compose up --build` y permite usar el panel sin claves.
- Procesa texto nuevo y ejemplos modificados; el mock no devuelve una fila por su ID.
- Representa datos desconocidos sin inventar hechos.
- Permite inspeccionar evidencia, corregir campos y conservar las correcciones al actualizar el tipo de incidente.
- Permite completar preguntas y derivar una carta persistida tras recargar.
- Informa fallos del LLM y permite continuar la carga manual.
- El repositorio y la imagen excluyen secretos, datos privados de ejecución y el PDF original.

## Fuera del alcance inicial

Audio, telefonía en tiempo real, despacho automático, integración real con CAD, geocodificación externa y operación en producción. Los protocolos de demostración no se presentan como validados para uso operativo.
