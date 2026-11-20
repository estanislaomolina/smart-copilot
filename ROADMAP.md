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

## Hito 1 — Contratos y servicio ejecutable

Rama sugerida: `feat/domain-foundation`.

- [ ] Modelar transcripción, ubicación, evidencia, tipología, prioridad y carta.
- [ ] Distinguir campos desconocidos, sugerencias y valores confirmados.
- [ ] Definir preguntas con identificador y estados pendiente, respondida, ambigua y no aplicable.
- [ ] Definir contrato común para proveedores y errores.
- [ ] Crear API mínima, healthcheck y Docker Compose.

Aceptación: el servicio arranca desde un entorno limpio y los contratos validan entradas, evidencia y estados inválidos. Solo se analiza texto; no se integra audio.

## Hito 2 — Recorrido completo en modo mock

Ramas sugeridas: `feat/mock-analysis` y `feat/operator-workflow`, como incrementos sucesivos.

- [ ] Cargar ejemplos y texto libre.
- [ ] Extraer mediante reglas deterministas y seleccionar protocolos del catálogo local.
- [ ] Mostrar datos, evidencia, preguntas e instrucciones en el panel.
- [ ] Permitir correcciones, respuestas y revisión de la carta.
- [ ] Persistir carta y revisiones en SQLite.
- [ ] Derivar al CAD simulado con confirmación e identificador visibles.

Aceptación: con `docker compose up --build`, sin claves ni servicios externos durante el uso, se completa el recorrido. Modificar la dirección de un ejemplo cambia el resultado; la carta persiste tras recargar y las correcciones humanas no se pierden al reanalizar.

## Hito 3 — LLM y controles de incertidumbre

Rama sugerida: `feat/llm-provider`.

- [ ] Integrar un proveedor real con configuración por entorno.
- [ ] Validar salida estructurada y fragmentos de evidencia.
- [ ] Separar afirmaciones del relato de inferencias.
- [ ] Aplicar tiempos de espera y reintentos acotados donde corresponda.
- [ ] Mostrar proveedor y fallos explícitos, conservando la posibilidad de carga manual.
- [ ] Tratar la transcripción como contenido, no como instrucciones del sistema.
- [ ] Mantener instrucciones de prearribo en un catálogo con procedencia y estado de revisión.

Aceptación: el proveedor real y el mock cumplen el mismo contrato. Entradas ambiguas, fallos de red y respuestas inválidas no generan una ficha aparentemente confirmada ni borran el trabajo del operador.

## Hito 4 — Evaluación reproducible

Rama sugerida: `feat/evaluation`.

- [ ] Auditar etiquetas antes de establecer resultados esperados.
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

Primero se completa el flujo obligatorio en mock; luego se integra el LLM y se evalúa. Las 72 horas son corridas desde la recepción: se reservan las últimas seis para documentación, video y contingencias, ajustando el alcance al tiempo real disponible.

Mapas, audio, geocodificación externa, múltiples proveedores reales y otros extras se consideran solo después de completar los hitos obligatorios.
