# Roadmap

## Forma de trabajo

El repositorio se mantiene privado durante el desarrollo. Al completar y verificar la entrega se hará público, conservando el historial y los pull requests.

- `main` contiene los hitos integrados y se mantiene utilizable conforme al estado del proyecto.
- Cada cambio coherente se desarrolla en una rama corta: `feat/...`, `fix/...`, `docs/...` o `chore/...`.
- Se abre un PR por incremento revisable, sin separar artificialmente cada archivo ni acumular toda la aplicación en uno.
- Cada PR explica problema, cambio, verificación y limitaciones. Mientras está incompleto se marca como draft.
- Antes del merge se revisa el diff, se ejecutan las comprobaciones pertinentes y se actualiza la documentación afectada.
- Se usa merge commit para conservar los commits y la relación con el PR. No se reescribe el historial para aparentar un proceso distinto.
- Al integrarse el cambio se elimina la rama remota; no se necesita una rama develop.
- Los fallos, resultados de evaluación y correcciones se documentan cuando ocurren. No se inventan métricas ni revisiones.
- No se añaden credenciales, respuestas privadas de proveedores ni transcripciones reales.

Un historial claro facilita revisar el trabajo, aunque la consigna no exige usar PRs. El requisito explícito es un historial de commits prolijo.

## Hito 0 — Base y planificación

Rama: `chore/project-roadmap`.

- [x] Inicializar Git y repositorio privado.
- [x] Incorporar el CSV sintético provisto, sin modificarlo.
- [x] Excluir secretos, datos de ejecución y PDF de la consigna.
- [x] Documentar arquitectura propuesta, roadmap y criterios de aceptación.
- [x] Integrar el PR inicial de planificación (PR #1).

## Hito 1 — Auditoría, contratos y servicio ejecutable

Ramas: `feat/dataset-audit` para la auditoría inicial y `feat/domain-foundation` para contratos y servicio.

- [x] Auditar estructura, cobertura y posibles inconsistencias sin modificar el contenido del CSV; incluir notebook visual con lógica en scripts Python.
- [x] Documentar uso de columnas y revisión puntual de etiquetas en [data-audit.md](docs/data-audit.md).
- [x] Preparar ocho casos sintéticos de desarrollo con evidencia y expectativas explícitas.
- [x] Modelar transcripción, ubicación, evidencia, tipología, prioridad y carta.
- [x] Distinguir campos desconocidos, sugerencias y valores confirmados.
- [x] Definir preguntas con identificador y estados pendiente, respondida, ambigua y no aplicable.
- [x] Definir contrato común para proveedores y errores.
- [x] Crear API mínima, healthcheck y Docker Compose.

Aceptación técnica verificada: el servicio se construye y arranca con Docker Compose; los contratos rechazan evidencia y estados inválidos. Ver [contratos y verificaciones](docs/domain-contracts.md). Los casos sintéticos quedan apartados; el desarrollo inicial utiliza el dataset provisto. Solo se contempla texto; no se integra audio.

## Hito 2 — Recorrido completo en modo mock

Ramas sugeridas: `feat/mock-analysis` y `feat/operator-workflow`, como incrementos sucesivos.

Primer incremento — `feat/mock-analysis`:

- [x] Implementar `POST /api/analyze` para recibir texto libre.
- [x] Extraer ubicación y sugerir categoría con reglas deterministas, evidencia y datos desconocidos explícitos.
- [x] Agregar tests de valores esperados revisados del CSV y errores de la API.
- [x] Agregar riesgos y prioridad de simulación con cobertura parcial; no se amplían reglas para perseguir 30/30.
- [x] Incorporar catálogo de demostración y selección por subtipo o por el operador.
- [x] Implementar checklist inicial con evidencia para diálogo explícito y conservación de respuestas manuales compatibles.
- [x] Separar la evaluación contextual del checklist y cubrir de forma conservadora presencia/atrapamiento con evidencia y aclaración versionada.

Incremento actual: `feat/call-card-persistence`, carta y SQLite sobre la conversación progresiva. Ver [catálogo y checklist](docs/protocol-engine.md) y [reglas de simulación](docs/mock-priority-risks.md). El recorrido mock del Hito 2 está completo. La carga directa de ejemplos se descartó como requisito del operador: es una comodidad de demo y se pueden pegar relatos manualmente. Las limitaciones semánticas del mock se mantienen explícitas.

- [x] Cargar texto libre y ejemplos pegados manualmente.
- [x] Extraer mediante reglas deterministas y seleccionar protocolos del catálogo local.
- [x] Mostrar datos, evidencia, preguntas e instrucciones en el panel.
- [x] Cargar texto libre con Enter, confirmar/corregir categoría y prioridad y elegir el tipo de incidente sin menús intermedios.
- [x] Agregar turnos y actualizar el historial completo, conservando decisiones humanas y protocolo compatible; mostrar discrepancias y preservar el trabajo ante errores.
- [x] Guía de atención: instrucciones del catálogo, próxima pregunta utilizable y checklist completo con revisión manual de estados.
- [x] Iniciar una guía general explícita por categoría conocida, sin bloquear por subtipo ni elegir arbitrariamente un protocolo específico.
- [x] Confirmar y corregir categoría, prioridad y cada campo de ubicación individualmente; conservar valores revisados y vaciados explícitos al actualizar y recuperar la llamada. Edición a demanda, sin confirmaciones permanentes ni obligación de revisar cada campo.
- [x] Permitir respuestas y revisión explícita de la carta, con resumen y observaciones editables.
- [x] Persistir carta, atención y revisiones en SQLite, con recuperación al recargar y control de versión.
- [x] Derivar al CAD simulado tras revisión, con fecha e identificador visibles y reintentos idempotentes.

Aceptación: con `docker compose up --build`, sin claves ni servicios externos durante el uso, se completa el recorrido. Modificar la dirección de un ejemplo cambia el resultado; la carta persiste tras recargar y las correcciones humanas se conservan al actualizar la guía del incidente.

### Próximos incrementos revisables

1. Conversación progresiva: turnos, combinación con decisiones manuales y actualización del checklist (implementado; mantiene las limitaciones semánticas del mock).
2. Guía y checklist: instrucciones, siguiente pregunta y revisión manual de estados implementadas; confirmaciones individuales de categoría, prioridad y ubicación implementadas.
3. Carta de Llamada y SQLite: guardar conversación, revisiones, selección de protocolo y decisiones humanas; revisión explícita y derivación simulada. Implementado, incluida revisión individual de categoría, prioridad y ubicación.
4. Evidencia resaltada en el texto y sugerencia de protocolo confirmable cuando haya evidencia suficiente; nunca elegir el primero por defecto.
5. Groq (Haiku opcional) sobre los mismos contratos y el mismo frontend, con proveedor activo visible.
6. Verificación integral, documentación y preparación de entrega.

## Hito 3 — LLM y controles de incertidumbre

Rama: `feat/groq-provider`, sobre los PRs del Hito 2 ya integrados. Integración y controles verificados mediante transporte controlado, comprobaciones reales acotadas con Groq y replay local de decisiones humanas. incident-v6 conserva los contratos del dominio; GPT-OSS 120B usa razonamiento medio. Se registró un intento inválido rechazado antes de obtener una extracción válida. Se completa el alcance de integración de este hito, sin afirmar precisión semántica ni generalización; esa evaluación continúa en el Hito 4.

- [x] Integrar Groq como proveedor real recomendado, con configuración por entorno y Haiku opcional.
- [x] Implementar evaluación semántica mediante el proveedor LLM, separada de protocolos y conservando revisión humana.
- [x] Completar comprobaciones puntuales de respuestas explícitas/descriptivas, incertidumbre, negaciones y correcciones. Se probaron presencia dentro, una descripción de heridos, negativas y dirección corregida con checklist posterior. La continuidad manual se verificó mediante replay de respuestas reales y SQLite temporal, sin una nueva inferencia ni un recorrido de navegador. Ver [registro de desarrollo](docs/hito3-development-checks.md); no es evaluación independiente ni una métrica de precisión.
- [x] Validar salida estructurada y fragmentos de evidencia.
- [x] Separar afirmaciones del relato de inferencias.
- [x] Aplicar tiempos de espera y reintentos acotados donde corresponda.
- [x] Mostrar proveedor y fallos explícitos, conservando la posibilidad de carga manual.
- [x] Tratar la transcripción como contenido, no como instrucciones del sistema.
- [x] Mantener instrucciones de prearribo en un catálogo con procedencia y estado de revisión.

Aceptación: el proveedor real y el mock cumplen el mismo contrato. Entradas ambiguas, fallos de red y respuestas inválidas no generan una ficha aparentemente confirmada ni borran el trabajo del operador.

## Hito 4 — Evaluación reproducible

Rama sugerida: `feat/evaluation`.

Incremento actual: rama `feat/evaluation`. El evaluador mide extracción y checklist por separado, conserva resultados parciales y genera entradas para revisión humana. Hay ocho casos reservados con expectativas y hash versionados. Se completaron los ocho casos una vez cada uno: tres coincidencias completas de comprobaciones, dos diferencias de ubicación y tres errores de salida inválida. Doce solicitudes en total, sin reintentos y con pausas; revisión asistida realizada y revisión humana independiente pendiente. No se cambió el sistema a partir del resultado. Ver [tandas y acumulado](docs/evaluation-results.md). Las verificaciones con Mock continúan usando los dos casos conocidos. Ver [protocolo y límites](docs/evaluation.md). La corrida inicial está terminada. Queda la revisión humana de expectativas e interpretaciones, resolver o documentar las limitaciones detectadas y preparar la evaluación final.

- [ ] Completar la revisión de etiquetas y protocolos antes de establecer resultados esperados; auditoría inicial en el Hito 1.
- [ ] Tras el primer extractor, decidir qué casos sintéticos adicionales aportan cobertura y revisar sus expectativas antes de usarlos.
- [x] Definir y versionar la separación entre desarrollo y evaluación; conjunto reservado v1 fijado antes de la primera tanda.
- [x] Añadir ocho casos propios reservados con negaciones, datos ausentes, direcciones nuevas, correcciones e intentos de alterar instrucciones; expectativas previas y hash versionado.
- [x] Mantener expectativas fuera de las entradas del proveedor en el comando de evaluación; verificación de esa separación sin red.
- [x] Ejecutar la primera evaluación de ubicación, categoría y estados del checklist, contabilizar salidas inválidas y revisar las salidas como agente. Prioridad sin clasificación automática en modo LLM; sin validación P1–P4.
- [ ] Completar revisión humana independiente de expectativas y soporte semántico; no sustituirla por coincidencia literal ni inspección del agente.
- [x] Implementar conteos, fallos, latencia por etapa e intentos observados. Consumo no disponible en el contrato: se registra null. Mediciones reales y revisión pendientes.
- [x] Distinguir resultados reales de pruebas mock; documentar muestra sintética pequeña, errores, revisión asistida y ausencia de P4 en el dataset original.

Aceptación: un comando documentado reproduce la evaluación y genera resultados identificando casos, proveedor y configuración. No se afirma generalización por subcategoría a partir de una sola muestra.

### Mejora de fiabilidad posterior

Se implementaron diagnósticos seguros por intento, medición explícita de cero/un reintento y extracción sola, protección contra sobrescritura de reportes y política de referencia para ubicaciones sin tipo determinado (incident-v7).
Los ocho casos observados se consideran desarrollo para ajustes posteriores. Se congelaron dos casos nuevos antes de consultarlos: uno completó seis comprobaciones y otro falló por formato incluso con el segundo intento. Ver [resultados completos e incidencia de ejecución](docs/llm-reliability-results.md).
No se declara una mejora general de precisión o fiabilidad. La política de ubicación ambigua se verificó con transporte controlado, pero su caso real reservado no produjo datos válidos. La línea base y los 30 registros originales quedan intactos.

## Hito 5 — Entrega

Rama sugerida: `chore/release-preparation`.

- [x] Probar arranque limpio, modo mock y persistencia. Verificación aislada con Compose en otro proyecto y puerto, sin tocar el contenedor ni el volumen existentes: panel, health, análisis, protocolo, guardado, revisión, derivación, recuperación, listado e historial respondieron correctamente.
- [ ] Al completar todo el flujo, ejecutar una corrida reproducible con los 30 registros del CSV y registrar resultados y fallos sin ajustar reglas para forzar coincidencias; son casos conocidos de desarrollo, no evaluación independiente.
- [x] Completar README y memoria de decisiones con resultados y limitaciones reales. Ver [decisiones](docs/decisions.md).
- [x] Revisar secretos y contenido de archivos, historial e imagen. Sin claves reales en archivos versionados; `.env`, PDF y SQLite nunca entraron al historial; la imagen no incluye credenciales, base de ejecución ni el PDF.
- [ ] Grabar video de 1–3 minutos: arranque, transcripción, asistencia, corrección y derivación.
- [ ] Hacer público el repositorio y verificar acceso sin autenticación.
- [ ] Crear un tag de entrega `v0.1.0` y comprobar enlaces.

Revisión técnica final sin nuevas funcionalidades: una salida inválida no modifica datos confirmados por el operador; ante un fallo del proveedor se puede continuar manualmente sin consultar a Groq; y la Carta de Llamada se guarda, revisa, recupera, lista, consulta en el historial y deriva con Groq configurado y caído. La prueba de regresión en `tests/test_calls.py` cubre esas operaciones dentro del bloque de caída; la demostración completa desde un arranque limpio de Docker en modo mock se verificó manualmente. No sustituye la revisión humana independiente ni mide precisión del modelo.

Aceptación: el evaluador puede clonar el repo, ejecutar el único comando requerido y completar el flujo sin credenciales. El video y la documentación corresponden al commit entregado.

## Prioridad y presupuesto

Primero se completa el flujo obligatorio en mock con catálogo y revisión humana; luego se integra Groq y se evalúa. Las 72 horas son corridas desde la recepción: se reservan las últimas seis para documentación, video y contingencias, ajustando el alcance al tiempo real disponible.

Mapas, audio, geocodificación externa, múltiples proveedores reales y otros extras se consideran solo después de completar los hitos obligatorios.
