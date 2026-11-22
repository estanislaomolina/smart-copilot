# Cierre de bloqueo de cuota y simplificación de categoría

El intento de retomar la corrida 120B confirmó HTTP 429 con TPD: límite de tokens diarios del modelo, no solo solicitudes por minuto. El proveedor indicó retry-after=681 para esa solicitud. La corrida original conserva cinco casos registrados y no se presenta como completada.

## Cambio técnico

incident-v8 conserva los contratos públicos, el enum de categoría, la evidencia literal y las validaciones de estado.
El formato de categoría enviado al LLM pasa de tres objetos anyOf casi idénticos a un único objeto con valor enum/null, origen, citas y justificación. Pydantic vuelve a verificar localmente las mismas tres combinaciones originales.
Categoría conocida sin citas, inferencia sin justificación y categoría desconocida con valor siguen rechazadas. No hay conversión de etiquetas inventadas ni inferencia de categoría por ID del CSV.
El objetivo es reducir la duplicación del esquema ante los rechazos observados en category. Es una corrección general de compatibilidad; no se afirma que elimine todos los fallos del proveedor.
Los diagnósticos distinguen también el atributo del contrato (value/origin/quotes/etc.), sin copiar valores o mensajes remotos.

El runner observa disponibilidad y restablecimiento de tokens por minuto en los encabezados. Con menos de 6000 disponibles espera su restablecimiento además de respetar el intervalo mínimo. Esa observación no permite deducir disponibilidad de tokens diarios ni reintenta un 429.

## Modelo y medición separados

Una prueba de desarrollo con Groq openai/gpt-oss-20b e incident-v8 respondió HTTP 200, pasó la validación y devolvió categoría y ubicación del relato, en 1,47 segundos de intento. Fue una sola extracción: no mide precisión general.
Se seleccionó ese modelo en la configuración local para continuar sin cambiar de proveedor ni activar Anthropic. La clave permanece local; no se cambió la facturación.
No se presenta una nueva corrida con modelo/esquema diferentes como continuación de los resultados 120B. Ambos conjuntos deben conservar modelo, prompt y configuración en sus manifiestos.
La corrida 120B/incident-v7 queda congelada e interrumpida. La siguiente corrida de los 30 es nueva y los casos siguen siendo desarrollo conocido.

Verificación local: 87 pruebas Python pasan, incluidas las combinaciones inconsistentes de categoría y el ritmo adaptado a encabezados de cuota. La prueba con 20B valida una respuesta, no garantiza que las 30 llamadas estén libres de errores.
