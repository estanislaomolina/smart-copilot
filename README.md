# Smart Copilot

Prototipo de asistencia para operadores de emergencias a partir de transcripciones de texto.

## Estado

Repositorio inicial y plan de trabajo. La aplicación todavía no está implementada. El comando de arranque de la entrega será `docker compose up --build`.

## Objetivo

El operador carga una transcripción, revisa ubicación, tipología y prioridad sugerida, completa el checklist y consulta instrucciones de prearribo. Puede corregir los datos y derivar una Carta de Llamada estructurada. El despachador decide los recursos; el copiloto no los despacha.

## Plan de implementación

1. **Contrato y dominio.** Definir esquemas, evidencia textual, datos desconocidos y estados de preguntas y cartas. Bocetar el panel y cerrar criterios de aceptación.
2. **Flujo completo con mock.** Implementar backend, panel y persistencia con Docker Compose. Cargar texto, analizar mediante reglas, editar, completar el checklist y derivar una carta persistida.
3. **Proveedor LLM real.** Integrar un proveedor detrás de la misma interfaz, con salida estructurada, validación y tiempos de espera. Mostrar el modo activo y los errores; no sustituir silenciosamente un fallo real por resultados mock.
4. **Controles de calidad.** Verificar evidencia, separar hechos de inferencias y conservar correcciones humanas. Seleccionar preguntas e instrucciones desde un catálogo versionado, sin generar libremente procedimientos de emergencia.
5. **Evaluación.** Probar casos adicionales reservados: negaciones, datos ausentes, correcciones del llamante, ubicaciones nuevas, instrucciones adversarias y fallos del proveedor. Reportar errores y limitaciones.
6. **Entrega.** Verificar arranque limpio y uso sin credenciales, completar documentación y grabar un video de 1–3 minutos hasta la derivación.

### Ventanas orientativas dentro de las 72 horas corridas

- 0–6 h: alcance, contratos y boceto.
- 6–24 h: flujo completo con mock y contenedores.
- 24–40 h: proveedor real y controles.
- 40–56 h: evaluación y correcciones prioritarias.
- 56–66 h: usabilidad y verificación.
- 66–72 h: documentación, video y margen.

Son ventanas de hitos, no 72 horas de trabajo continuo. Hay que ajustarlas al tiempo restante desde la recepción.

## Arquitectura propuesta

- Backend: Python, FastAPI y Pydantic.
- Panel: React y TypeScript.
- Persistencia: SQLite para cartas y revisiones.
- Proveedores: mock determinista y un proveedor LLM real.
- Protocolos: catálogo local versionado con procedencia y estado de revisión.
- Ejecución: Docker Compose, sin servicios externos necesarios durante el uso del modo mock.

Flujo: transcripción → extracción → validación → selección de protocolo → revisión humana → carta persistida. La derivación a CAD será simulada e identificada como tal.

Fine-tuning, múltiples agentes y bases vectoriales quedan fuera del alcance inicial.

## Datos y publicación

La consigna describe los registros como sintéticos. Eso no establece por sí mismo permiso de redistribución del material de la empresa. El CSV original y el PDF quedan excluidos de Git y del contexto de construcción Docker. Es una decisión preventiva, no una afirmación de que contengan datos personales reales.

- Se crearán ejemplos sintéticos propios, identificados como tales, sin copiar registros originales.
- La carga del CSV provisto será opcional y local; no será requisito para ejecutar la demostración.
- No se publicarán transcripciones, etiquetas ni protocolos derivados del material original sin revisar su autorización.
- Las claves se configurarán por variables de entorno; solo se versionará una plantilla sin secretos.
- El modo mock no enviará datos a terceros. Un proveedor remoto requerirá configuración explícita y será visible en el panel.
- Las trazas no almacenarán transcripciones completas por defecto.
- Antes de publicar se revisarán archivos, historial, capturas y video. Un repo privado también requiere controlar lo que se sube.

## Evaluación prevista

El dataset es pequeño y no cubre todas las prioridades. Algunas etiquetas agregan información ausente del relato y las listas de preguntas no siempre son complementarias. Se revisarán las referencias antes de usarlas como resultados esperados.

Se separarán ejemplos de desarrollo y casos reservados. Un caso usado en el prompt o disponible como referencia recuperable no se presentará como evaluación independiente.

Se reportarán exactitud de ubicación y categoría, confusiones de prioridad, preguntas marcadas como respondidas sin evidencia, afirmaciones sin respaldo, validez de salidas, errores, latencia y consumo. Se incluirán conteos y límites del tamaño de muestra.

## Criterios de aceptación

- Arranca con `docker compose up --build` y permite usar el panel sin claves.
- Procesa texto nuevo y ejemplos modificados; el mock no devuelve una fila por su ID.
- Representa datos desconocidos sin inventar hechos.
- Permite inspeccionar evidencia, corregir campos y conservar las correcciones al reanalizar.
- Permite completar preguntas y derivar una carta persistida tras recargar.
- Informa fallos del LLM y permite continuar la carga manual.
- El repositorio y la imagen excluyen secretos y material original.

## Fuera del alcance inicial

Audio, telefonía en tiempo real, despacho automático, integración real con CAD, geocodificación externa y operación en producción. Los protocolos de demostración no se presentan como validados para uso operativo.
