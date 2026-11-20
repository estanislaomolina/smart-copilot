"""Lectura del catálogo derivado; no consulta transcripciones del CSV."""

import re
import unicodedata
from pathlib import Path

from backend.domain.models import Category
from backend.protocols.models import CatalogFile, ProtocolDefinition, ProtocolError, ProtocolSummary

DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "data/protocols/demo.json"


def canonical(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(re.sub(r"[^\w]+", " ", "".join(
        char for char in folded if not unicodedata.combining(char)
    )).split())


class ProtocolCatalog:
    def __init__(self, path: Path = DEFAULT_CATALOG):
        self.document = CatalogFile.model_validate_json(path.read_text(encoding="utf-8"))
        self.protocols = {protocol.id: protocol for protocol in self.document.protocols}

    def summaries(self, category: Category | None = None) -> list[ProtocolSummary]:
        return [protocol.summary() for protocol in self.protocols.values()
                if category is None or protocol.category == category]

    def get(self, protocol_id: str) -> ProtocolDefinition:
        try:
            return self.protocols[protocol_id]
        except KeyError:
            raise ProtocolError("protocol_not_found") from None
