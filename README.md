# Smart Copilot

Prototipo de asistencia para operadores de emergencias a partir de transcripciones de texto.

## Estado

Planificación y auditoría inicial de datos disponibles. La aplicación todavía no está implementada. El comando de arranque de la entrega será `docker compose up --build`.

## Objetivo

El operador carga una transcripción, revisa ubicación, tipología y prioridad sugerida, completa el checklist y consulta instrucciones de prearribo. Puede corregir los datos y derivar una Carta de Llamada estructurada. El despachador decide los recursos; el copiloto no los despacha.

## Roadmap y forma de trabajo

Ver [ROADMAP.md](ROADMAP.md) para hitos, criterios de aceptación y flujo de ramas y pull requests.

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

Los [ocho casos sintéticos de desarrollo](data/synthetic/development.json) especifican comportamientos a revisar antes de implementar los proveedores. No son un conjunto reservado ni resultados de evaluación de un modelo.

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
- Permite inspeccionar evidencia, corregir campos y conservar las correcciones al reanalizar.
- Permite completar preguntas y derivar una carta persistida tras recargar.
- Informa fallos del LLM y permite continuar la carga manual.
- El repositorio y la imagen excluyen secretos, datos privados de ejecución y el PDF original.

## Fuera del alcance inicial

Audio, telefonía en tiempo real, despacho automático, integración real con CAD, geocodificación externa y operación en producción. Los protocolos de demostración no se presentan como validados para uso operativo.
