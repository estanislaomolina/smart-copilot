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
- [ ] Completar la interpretación de respuestas implícitas en relato libre, con revisión humana.

Incremento actual: `feat/operator-panel`, primer panel de consulta y confirmación de categoría/prioridad. Ver [catálogo y checklist](docs/protocol-engine.md) y [reglas de simulación](docs/mock-priority-risks.md). El Hito 2 sigue abierto hasta completar el recorrido del operador.

- [ ] Cargar ejemplos y texto libre.
- [x] Extraer mediante reglas deterministas y seleccionar protocolos del catálogo local.
- [x] Mostrar datos, evidencia, preguntas e instrucciones en el panel.
- [x] Cargar texto libre con Enter, confirmar/corregir categoría y prioridad y elegir el tipo de incidente sin menús intermedios.
- [ ] Editar ubicación y completar respuestas desde el panel.
- [ ] Permitir correcciones, respuestas y revisión de la carta.
- [ ] Persistir carta y revisiones en SQLite.
- [ ] Derivar al CAD simulado con confirmación e identificador visibles.

Aceptación: con `docker compose up --build`, sin claves ni servicios externos durante el uso, se completa el recorrido. Modificar la dirección de un ejemplo cambia el resultado; la carta persiste tras recargar y las correcciones humanas se conservan al actualizar la guía del incidente.

## Hito 3 — LLM y controles de incertidumbre

Se retoma con Haiku después de completar el Hito 2.

- [ ] Integrar Haiku como proveedor real con configuración por entorno.
- [ ] Validar salida estructurada y fragmentos de evidencia.
- [ ] Separar afirmaciones del relato de inferencias.
- [ ] Aplicar tiempos de espera y reintentos acotados donde corresponda.
- [ ] Mostrar proveedor y fallos explícitos, conservando la posibilidad de carga manual.
- [ ] Tratar la transcripción como contenido, no como instrucciones del sistema.
- [ ] Mantener instrucciones de prearribo en un catálogo con procedencia y estado de revisión.

Aceptación: el proveedor real y el mock cumplen el mismo contrato. Entradas ambiguas, fallos de red y respuestas inválidas no generan una ficha aparentemente confirmada ni borran el trabajo del operador.

## Hito 4 — Evaluación reproducible

Rama sugerida: `feat/evaluation`.

- [ ] Completar la revisión de etiquetas y protocolos antes de establecer resultados esperados; auditoría inicial en el Hito 1.
- [ ] Tras el primer extractor, decidir qué casos sintéticos adicionales aportan cobertura y revisar sus expectativas antes de usarlos.
- [ ] Definir y versionar la separación entre desarrollo y evaluación.
- [ ] Añadir casos propios reservados con negaciones, datos ausentes, direcciones nuevas, correcciones e intentos de alterar instrucciones.
- [ ] Evitar que las respuestas o filas completas de evaluación se filtren al prompt o a la recuperación.
- [ ] Evaluar ubicación, categoría, prioridad, checklist y afirmaciones sin respaldo.
- [ ] Reportar conteos, fallos, latencia y consumo cuando esté disponible.
- [ ] Distinguir resultados reales de pruebas mock; documentar cobertura limitada y ausencia de P4 en el dataset original.

Aceptación: un comando documentado reproduce la evaluación y genera resultados identificando casos, proveedor y configuración. No se afirma generalización por subcategoría a partir de una sola muestra.

## Hito 5 — Entrega

Rama sugerida: `chore/release-preparation`.

- [ ] Probar arranque limpio, modo mock y persistencia.
- [ ] Completar README y memoria de decisiones con resultados y limitaciones reales.
- [ ] Revisar secretos y contenido de archivos, historial e imagen.
- [ ] Grabar video de 1–3 minutos: arranque, transcripción, asistencia, corrección y derivación.
- [ ] Hacer público el repositorio y verificar acceso sin autenticación.
- [ ] Crear un tag de entrega `v0.1.0` y comprobar enlaces.

Aceptación: el evaluador puede clonar el repo, ejecutar el único comando requerido y completar el flujo sin credenciales. El video y la documentación corresponden al commit entregado.

## Prioridad y presupuesto

Primero se completa el flujo obligatorio en mock con catálogo y revisión humana; luego se integra Haiku y se evalúa. Las 72 horas son corridas desde la recepción: se reservan las últimas seis para documentación, video y contingencias, ajustando el alcance al tiempo real disponible.

Mapas, audio, geocodificación externa, múltiples proveedores reales y otros extras se consideran solo después de completar los hitos obligatorios.
