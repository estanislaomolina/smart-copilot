# Verificación preliminar de los 30 registros del CSV (solo extracción)

Esta corrida se ejecutó el 21 de noviembre de 2026 con Groq sobre los **30 casos conocidos del CSV provisto**. Es una comprobación intermedia de solo extracción; la corrida final con el corredor versionado se documenta aparte en [final-csv-run.md](final-csv-run.md). Son material de desarrollo: **no es una evaluación independiente** ni una medición de precisión general. No se ajustaron reglas, prompts ni expectativas a partir del resultado.

## Configuración

| Campo | Valor |
|---|---|
| Proveedor | `groq` (`openai/gpt-oss-120b`, razonamiento medio) |
| Modo | Solo extracción (`--extract-only`), sin consulta al checklist |
| Reintentos | 0 (`max_retries=0`) |
| Timeout | 20 s por intento |
| Casos | 30, generados desde `data/raw/dataset_challenge_soflex.csv` sin modificarlo |
| Hash de casos | `9f26fcb8601f53fe1f35628841fa8c4648da4205d9aec038be5d0c6f7c9f0020` |
| Reporte consolidado | `artifacts/evaluation/dataset-30-groq-merged.json` (fuera de Git) |

Las expectativas son comparaciones literales tomadas de las columnas `categoria`, `subcategoria`, `calle_detectada`, `altura_detectada`, `interseccion_detectada` y `barrio_comuna`. No se compara prioridad: el proveedor LLM no asigna P1–P4 sin una política operativa validada. Los 30 relatos y sus etiquetas son los del CSV original.

## Resultados

| Estado | Casos |
|---|---:|
| Pasaron todas las comparaciones | 0 |
| Fallaron al menos una comparación | 19 |
| Error de salida inválida | 11 |
| Omitidos por límite de proveedor | 0 |

Comparaciones literales sobre los 19 casos con salida válida:

| Grupo | Coincidencias / comparadas |
|---|---:|
| Categoría | 13 / 19 |
| Subcategoría | 0 / 19 |
| Ubicación (calle, altura, intersección y localidad) | 24 / 76 |
| Casos con los cuatro campos de ubicación coincidentes | 0 / 19 |

Diagnóstico de intentos:

- 30 intentos observados en 30 casos: 19 salidas válidas, 7 rechazos por esquema remoto y 4 por validación local.
- Ningún caso se recuperó dentro del presupuesto de reintentos, porque se fijó en cero para esta corrida.
- Latencia de extracción: mínimo 2,87 s, mediana 3,54 s, máximo 5,77 s. No se midieron consumo de tokens ni tiempo de navegador.

Las 125 entradas de revisión quedaron en `pending`. No se revisaron semánticamente: una coincidencia literal no demuestra soporte en el relato y una diferencia literal no demuestra error semántico.

## Límites y lectura de los números

- El CSV contiene etiquetas enriquecidas: por ejemplo, intersecciones y localidades que no siempre aparecen en el relato. La auditoría del dataset ya lo documenta. Por eso estas comparaciones no se presentan como exactitud del modelo.
- La subcategoría del CSV es una descripción libre (`Incendio en Comercio Gastronómico`) mientras el extractor devuelve una categoría operativa corta o ninguna; la ausencia de coincidencia literal no implica que el relato haya sido mal interpretado.
- Once salidas fueron rechazadas por contrato antes de publicarse. El comportamiento es el esperado: una salida inválida no se convierte en datos confirmados.
- El primer intento sin pausas entre casos produjo dos salidas inválidas y un HTTP 429 que omitió los 27 casos restantes. Ese reporte quedó registrado por separado como `dataset-30-groq-sin-pausas.json` y no se mezcla con el consolidado. La corrida final usó pausas de 35 segundos entre casos, sin 429.
- No se corrigió ningún caso, etiqueta ni regla para mejorar estos números. No se afirma precisión, tasa de alucinaciones ni aptitud operativa.

## Reproducción

Los artefactos quedan fuera de Git. Desde la raíz del repositorio, con `GROQ_API_KEY` exportada localmente:

~~~bash
python3 scripts/build_dataset30_cases.py
mkdir -p artifacts/evaluation/dataset-30-runs
ids=$(python3 -c "import json; print(' '.join(c['id'] for c in json.load(open('artifacts/evaluation/dataset-30-cases.json'))['cases']))")
for id in $ids; do
  python3 scripts/evaluate.py --cases artifacts/evaluation/dataset-30-cases.json \
    --provider groq --case "$id" --limit 1 --extract-only \
    --output "artifacts/evaluation/dataset-30-runs/$id.json" || true
  sleep 35
done
python3 scripts/evaluate.py --merge-reports artifacts/evaluation/dataset-30-runs/*.json \
  --output artifacts/evaluation/dataset-30-groq.json
~~~

Si un caso devuelve `provider_rate_limited`, esperar y volver a ejecutar solo ese ID antes de consolidar. El script de generacion rechaza sobrescribir el conjunto de casos salvo `--overwrite` explicito.
