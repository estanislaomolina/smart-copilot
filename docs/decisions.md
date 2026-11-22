# Memoria de decisiones

Decisiones de ingeniería del prototipo y sus consecuencias. No son políticas operativas ni validación clínica. El alcance y los hitos están en [ROADMAP.md](../ROADMAP.md); los contratos, en [domain-contracts.md](domain-contracts.md).

## Stack y ejecución

- **FastAPI + Pydantic** en el backend y **React + TypeScript + Vite** en el panel. Elección estándar para validar contratos en los límites y mostrar evidencia sin añadir un framework mayor.
- **SQLite local** para cartas, revisiones y comprobantes. Permite demostrar persistencia y control de versión sin servicios externos. No tiene autenticación ni política de retención: es un prototipo local, no apto para operación real.
- **Docker Compose** con dos etapas: compila el panel con Node y sirve el resultado desde FastAPI. El modo mock no necesita claves ni red. La base queda en un volumen separado y no entra en la imagen.

## Proveedor y datos

- **Mock determinista por defecto.** El proveedor real se activa solo con configuración explícita y se muestra en el encabezado y `/api/config`. Nunca se sustituye silenciosamente uno por otro.
- **Groq recomendado, Haiku opcional.** Ambos cumplen el mismo contrato y usan HTTPX el primero y el SDK oficial el segundo, sin dependencias innecesarias. No se cambió la política de reintentos del producto para medir la evaluación.
- **El LLM no asigna prioridad P1–P4.** Sin política operativa validada, la prioridad queda desconocida hasta revisión humana. Las reglas del mock son demostrativas y no se trasladaron a los prompts.
- **Instrucciones desde el catálogo local**, con procedencia y estado `demo_unverified`. Las preguntas e instrucciones nunca se generan en el proveedor ni se toman de las respuestas esperadas del CSV.
- **Citas literales y offsets calculados localmente.** El proveedor no calcula índices; una cita ausente, repetida sin contexto, esquema inválido o pregunta ajena al catálogo se rechaza. Esto comprueba procedencia, no corrección semántica.
- **Un reintento acotado y sin reintento para HTTP 429 en Groq.** Ante cuota agotada se informa y se ofrece carga manual. La corrección de salidas rechazadas usa el mismo presupuesto sin reenviar la generación inválida como instrucción.

## Robustez frente a fallos

- **Una salida inválida no publica datos.** El backend valida esquema y transcripción antes de responder; el frontend solo reemplaza el estado visible cuando extracción y protocolo terminan correctamente. Ante un fallo se conservan conversación, correcciones, protocolo y turnos sin incorporar.
- **Las decisiones humanas prevalecen.** Los campos con origen `operator`, los vaciados explícitos y las respuestas revisadas se conservan al anexar turnos o recalcular la guía; si la sugerencia automática difiere, se muestra un aviso en lugar de sobrescribir.
- **Continuación manual explícita.** Tras un fallo del proveedor, `manual_only` produce un checklist pendiente sin consultar al proveedor. Es una acción de la interfaz, no un cambio silencioso a mock.
- **La Carta de Llamada es independiente del proveedor.** Guardado, revisión, recuperación, listado, historial y derivación simulada usan solo SQLite y el catálogo. Con Groq configurado y caído, `/api/analyze` responde 503 y esas operaciones responden 200; la prueba automatizada las cubre dentro del bloque de caída. El arranque limpio con Docker en modo mock se comprobó manualmente.

## Evaluación

- **Separación desarrollo/evaluación con hash versionado.** Los ocho casos de la línea base pasaron a desarrollo tras el cambio a incident-v7; dos casos nuevos se congelaron antes de consultar proveedores. Las expectativas nunca se envían al modelo.
- **Reportes sin secretos ni transcripciones completas.** Se guardan fuera de Git; los resúmenes versionados conservan conteos, tiempos, hashes y fallos. El consumo no está en el contrato y se registra como `null`.
- **Coincidencia literal ≠ soporte semántico.** Las entradas de revisión empiezan en `pending`. La inspección de 38 entradas realizada a pedido del propietario es de agente (`independent_human_review: false`): 34 respaldadas, 4 inciertas, 0 sin respaldo. La revisión humana independiente sigue pendiente.
- **Muestra pequeña y fallos visibles.** Tres errores de salida inválida y dos diferencias de ubicación en la línea base, más un caso nuevo que falla con corrección. No se afirma precisión general, tasa de alucinaciones ni validez operativa. La verificación preliminar de solo extracción sobre los 30 registros del CSV dejó 19 casos con diferencias, 11 salidas inválidas y ninguna omisión; ver [resultados](dataset-30-results.md). La corrida final con el corredor versionado se ejecuta aparte, sin reutilizar esos números como resultado definitivo.

## Fuera del alcance

Audio, telefonía, despacho automático e integración real con CAD, geocodificación externa, autenticación, bases vectoriales y ajuste de modelos. Las derivaciones están identificadas como simulación y los protocolos como demostración.

## Cierre

La revisión final no añadió funcionalidades: se concentró en las tres condiciones de robustez del proveedor y en el arranque limpio con Docker en modo mock. La verificación preliminar de los 30 registros con Groq quedó documentada; la corrida final del corredor versionado está en ejecución. Siguen pendientes el cierre de esa corrida, el video, la publicación del repositorio y el tag; la revisión humana independiente tampoco se sustituye por la inspección de agente. El prototipo se presenta con esas limitaciones explícitas, no como un sistema validado para emergencias reales.
