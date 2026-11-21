# Resultados de los cuatro cambios de fiabilidad

La implementación de diagnóstico, medición y política de ubicación quedó en 9796573.
Los nuevos casos se congelaron antes de consultar proveedores en 1127c51.
e83024b añadió diagnóstico local de la generación rechazada y protección de reportes.
Prompt: incident-v7; modelo openai/gpt-oss-120b, razonamiento medium. La línea base de ocho casos sigue intacta en evaluation-results-v1.json.

## 1. Diagnóstico sin datos sensibles

Se registran eventos por intento con resultado, tiempo, HTTP y tipos de validación asociados al campo raíz. No se registran transcripciones, valores, citas, claves o cuerpos remotos en esos eventos.
La sonda de desarrollo posterior encontró un rechazo remoto con incompatibilidades de tipos/literales en category. No se afirma qué etiqueta exacta generó el modelo ni se reconstruye la causa de los errores históricos sin datos.
La generación rechazada se valida localmente solo para producir códigos seguros. Nunca se publica ni se manda al modelo para corregirla.

## 2. Corrección acotada medida

Se ejecutó el caso ya conocido DEV-RELIABILITY-06 en extracción sola:
- Cero reintentos: una solicitud, salida inválida por citas inexistentes en señales/resumen; 3,269931 segundos de extracción.
- La corrida de desarrollo conservada con un reintento habilitado: válida en el primer intento, cinco coincidencias literales; 3,304051 segundos. No activó la corrección.

No se atribuye esa diferencia al reintento: son generaciones distintas y la salida válida no necesitó el segundo intento.
Los transportes controlados sí verifican recuperación tras cita inválida y rechazo remoto, y que dos fallos agotan el presupuesto sin publicar datos. En el nuevo caso reservado V2-01 se activó el único reintento, pero ambos intentos fueron rechazados: el corrector no garantiza recuperación.

## Incidencia de ejecución

Una sesión de ejecución terminó en el cliente mientras el proceso del contenedor continuaba. Al retomarla se repitió accidentalmente la corrida de desarrollo con un reintento y se sobrescribió su reporte anterior.
La repetición conservada no es evaluación independiente. No se reconstruye ni inventa el resultado perdido. Se cambió el comando para rechazar destinos existentes antes de enviar solicitudes, salvo --overwrite explícito.
Los dos reportes reservados se conservaron de su primera corrida; no se repitieron para obtener coincidencias.

Hay siete solicitudes de transporte documentadas en los reportes conservados de desarrollo, sonda y conjunto nuevo. La ejecución de desarrollo cuyo reporte se perdió puede haber usado una o dos solicitudes adicionales, según su presupuesto. No se presenta un conteo global exacto ni se estima consumo de tokens o costo.

## 3. Ubicación ambigua

La instrucción general conserva un nombre cuyo tipo no se pueda determinar en reference, con justificación; street y district quedan desconocidos. No hay reglas por nombres.
La conversión de ese estado y sus citas se comprobó localmente con un transporte controlado. El caso real reservado de ambigüedad no produjo una salida válida, por lo que la mejora semántica aún no está demostrada en él.
El segundo caso nuevo, con calle y localidad expresamente identificadas, sí conservó ambos componentes correctamente. Eso no prueba el comportamiento ante nombres sin tipo.

## 4. Nuevo conjunto independiente del ajuste

holdout-v2 contiene dos casos propios definidos después del cambio y congelados antes de ejecutar proveedores; su hash permanece intacto.
La primera corrida usó un máximo de un reintento por etapa:
- V2-01: error en extracción; dos rechazos remotos de esquema y cero consultas de checklist. No hay datos para puntuar ubicación o atrapamiento.
- V2-02: extracción y checklist válidos en sus primeros intentos; seis coincidencias literales. Respuestas negativas coherentes con la salida autónoma y ausencia de heridas/peligro del relato.

Fueron cuatro solicitudes observadas para el conjunto nuevo, una corrección intentada y ninguna etapa recuperada por reintento.
V2-02 tardó 3,374543 segundos en extracción y 2,730408 en checklist; total 6,10503 segundos.
V2-01 tardó 56,818645 segundos totales, incluidos 49,716659 de espera preventiva local por cupo. Esa espera pertenece al arnés de evaluación, no a la aplicación; no se debe interpretar el total como latencia pura del modelo.
No se cambiaron prompts, reglas, expectativas o catálogo entre ambos casos. La sonda posterior de V2-01 se copió explícitamente a desarrollo y no reemplaza su primer resultado.

El resumen sin transcripciones ni cuerpos remotos está en evaluation-results-v2.json; los reportes completos permanecen ignorados en artifacts/evaluation.
No se compara un porcentaje de estos dos casos contra el de los ocho anteriores: difieren entradas y configuración de reintentos y la muestra es mínima.
En inspección asistida del caso válido, las respuestas y dirección son coherentes con el relato. Las citas adjuntas al resumen no abarcan todos sus detalles, aunque estos aparecen en el resto de la conversación. Las ocho entradas siguen pendientes de revisión humana independiente.
La línea base sigue mostrando tres coincidencias completas, dos diferencias de ubicación y tres errores. No se borra ni se presenta la nueva corrida como una garantía de mejora global.

## Estado de entrega

Los cuatro cambios están implementados. Pasan 83 pruebas Python y Docker Compose fue reconstruido y quedó saludable.
Persisten errores de formato, incluso con una corrección; deben mantenerse explícitos antes de prometer fiabilidad. No se relajaron validaciones, no se amplió el Mock y no se entrenó con etiquetas.
La revisión humana y la validación operativa siguen pendientes. Los 30 registros originales todavía no se ejecutaron. No hubo push.
