# Contratos iniciales y servicio mínimo

Este documento registra la base técnica entregada en el Hito 1: contratos y arranque con Docker Compose. El estado actual de la extracción se documenta en [mock-analysis.md](mock-analysis.md); panel, persistencia y transiciones siguen pendientes.

## Datos y evidencia

La entrada es `AnalysisRequest.transcript`, texto no vacío de hasta 50.000 caracteres. Se conserva tal como se recibió, sin recortar espacios, para que las posiciones de evidencia sigan siendo válidas. El límite acota la entrada del prototipo; no representa una restricción del dominio.

Cada `FieldValue` distingue cuatro procedencias:

- `unknown`: valor nulo y sin evidencia.
- `transcript`: valor extraído o normalizado, con evidencia del relato.
- `inference`: sugerencia inferida, con evidencia y justificación; por ejemplo una prioridad.
- `operator`: dato confirmado o corregido por el operador, incluso si no figura en la transcripción.

Una evidencia contiene texto y offsets de caracteres Python, con inicio inclusivo y fin exclusivo. Se valida tanto la longitud como su coincidencia exacta con el relato original. Esto comprueba trazabilidad, no que el fragmento implique semánticamente la conclusión. Esa comprobación corresponde a reglas, evaluación y revisión humana.

Por ejemplo, sobre `Corrientes 1540`, el número se representa así:

```json
{
  "value": "1540",
  "origin": "transcript",
  "evidence": [{"text": "1540", "start": 11, "end": 15}]
}
```

La ubicación admite calle, altura textual, intersección, referencia y barrio/comuna, cada uno desconocido por defecto. La altura textual conserva S/N o referencias kilométricas sin forzar un entero. Categoría y prioridad se restringen al dominio previsto; subcategoría permanece textual por la cobertura limitada del CSV.

Los campos inesperados se rechazan. Las validaciones entre campos se implementan en Pydantic; permiten rechazar combinaciones incoherentes, además de validar tipos. [Documentación de validadores](https://pydantic.dev/docs/validation/latest/concepts/validators/).

## Preguntas e instrucciones

Las preguntas tienen ID estable, texto y estado `pending`, `answered`, `ambiguous` o `not_applicable`. La respuesta es textual para conservar negaciones y matices:

- Una pregunta pendiente no tiene respuesta, procedencia ni evidencia.
- Una respondida requiere respuesta y procedencia.
- Si proviene del relato, requiere evidencia verificable.
- Ambigüedad y no aplicabilidad requieren justificación.
- No se admiten IDs de preguntas duplicados en un incidente.

Las instrucciones de prearribo se modelan aparte con ID, protocolo, versión, fuente y estado de revisión. El resultado del extractor no tiene un campo de instrucciones libres. La carga del catálogo y su selección aún no están implementadas; tener este contrato no valida clínicamente su contenido.

## Proveedores y revisión humana

`ExtractionProvider` define una operación asíncrona `analyze(AnalysisRequest) -> AnalysisResult`. En el Hito 1 no había implementación mock ni real; el mock parcial se agrega en el Hito 2. El resultado identifica proveedor, modelo opcional y advertencias, y no permite atribuir datos al operador.

`CallCard` permite datos de procedencia humana, tiene ID, revisión numérica y estados `draft`, `reviewed` y `referred`. Las fechas tienen zona horaria, orden coherente y deben corresponder al estado.

Estos modelos validan snapshots; no implementan persistencia, control de acceso ni transiciones. La aplicación deberá gestionar las revisiones y conservar las correcciones al reanalizar. No se exige completar todas las preguntas para representar una carta revisada: la política de derivación se definirá en el flujo del operador.

Los códigos previstos para errores distinguen entrada inválida, proveedor no disponible, timeout, salida inválida y configuración no soportada. La traducción de fallos de extracción a HTTP se agrega con el proveedor mock en el Hito 2.

## Ejecución

```bash
docker compose up --build
```

- `http://localhost:8000/health`: estado de la API; no indica que un extractor esté operativo.
- `http://localhost:8000/docs`: documentación de los endpoints disponibles.
- `http://localhost:8000/contracts`: JSON Schema de los cuatro contratos públicos.
- `http://localhost:8000/`: enlaces del servicio.

El puerto puede cambiarse con `APP_PORT`; `.env.example` documenta la configuración, pero no hace falta copiarlo para arrancar. La única configuración admitida por ahora es `LLM_PROVIDER=mock`; un valor diferente produce un fallo explícito de arranque, en lugar de aparentar que hay un proveedor real.

La imagen copia únicamente requisitos y backend y ejecuta el proceso sin privilegios de root. El primer build requiere descargar la imagen base y dependencias; después, el servicio no necesita credenciales ni llamadas externas. La aplicación usa su propia imagen Python, siguiendo el despliegue de FastAPI en contenedores. [Documentación de Docker en FastAPI](https://fastapi.tiangolo.com/deployment/docker/).

## Verificación de este incremento

Se ejecutaron comprobaciones directas, sin incorporar una suite de tests:

- Serialización y lectura de contratos válidos.
- Rechazo de entradas vacías, campos extra, datos sin procedencia, evidencia ajena al relato, inferencias sin justificación, atribución humana desde un proveedor, preguntas incoherentes o duplicadas y cartas derivadas sin revisión.
- Aceptación de una respuesta negativa explícita y una carta con fechas coherentes.
- Construcción y arranque reales con Compose en el puerto de verificación 18080, con healthcheck saludable.
- Respuestas HTTP 200 de salud, contratos, documentación y OpenAPI dentro del contenedor.

La comprobación del panel y del recorrido completo corresponde al siguiente hito.
