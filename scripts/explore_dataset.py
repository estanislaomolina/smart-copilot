"""Presentación opcional para el notebook; la auditoría vive en audit_dataset.py."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from scripts.audit_dataset import DEFAULT_DATASET, PRIORITIES


def preview_dataset() -> pd.DataFrame:
    data = pd.read_csv(DEFAULT_DATASET, dtype=str, keep_default_na=False)
    return data[["id_registro", "categoria", "prioridad_sugerida",
                 "calle_detectada", "altura_detectada"]].head(5)


def dataset_overview(report: dict) -> pd.DataFrame:
    return pd.DataFrame({
        "Indicador": ["Registros", "Columnas", "IDs únicos", "Relatos únicos",
                      "Celdas vacías", "Subcategorías", "Errores detectados"],
        "Cantidad": [report["rows"], len(report["columns"]), report["unique_ids"],
                     report["unique_transcripts"], report["empty_cells"],
                     len(report["distributions"]["subcategoria"]), report["errors"]],
    })


def plot_distribution(report: dict, field: str, title: str) -> None:
    counts = report["distributions"][field]
    if field == "prioridad_sugerida":
        counts = {priority: counts.get(priority, 0) for priority in PRIORITIES}
    labels, values = list(counts), list(counts.values())
    fig, ax = plt.subplots(figsize=(9, 4))
    bars = ax.barh(labels, values, color="steelblue")
    ax.bar_label(bars, padding=4)
    ax.invert_yaxis()
    ax.set(title=title, xlabel="Cantidad de registros",
           ylabel="Prioridad sugerida" if field == "prioridad_sugerida" else "Categoría")
    ax.set_xlim(0, max(values) * 1.15)
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.01,
             f"Fuente: {report['source']['file']} · {report['rows']} registros sintéticos. "
             "Conteos del archivo completo.", fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    plt.show()
    plt.close(fig)


def findings_overview(report: dict) -> pd.DataFrame:
    return pd.DataFrame(list(report["finding_counts"].items()),
                        columns=["Señal de revisión o error", "Cantidad"])


def findings_for(report: dict, code: str) -> pd.DataFrame:
    return pd.DataFrame(
        [finding for finding in report["findings"] if finding["code"] == code],
        columns=["record", "field", "detail", "severity", "code"],
    )


def record_detail(record_id: str) -> pd.DataFrame:
    data = pd.read_csv(DEFAULT_DATASET, dtype=str, keep_default_na=False)
    fields = ["transcripcion_cruda", "calle_detectada", "altura_detectada",
              "interseccion_detectada", "preguntas_protocolo_mandatorias",
              "preguntas_respondidas_en_relato", "preguntas_pendientes"]
    selected = data.loc[data["id_registro"] == record_id, fields]
    if selected.empty:
        raise ValueError(f"Registro desconocido: {record_id}")
    return selected.T.rename(columns={selected.index[0]: record_id})
