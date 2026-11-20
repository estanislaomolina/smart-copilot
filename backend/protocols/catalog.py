"""Lectura del catálogo derivado; no consulta transcripciones del CSV."""

import re
import unicodedata
from pathlib import Path

from backend.domain.models import Category
from backend.protocols.models import CatalogFile, FollowUpCatalog, ProtocolDefinition, ProtocolError, ProtocolSummary

DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "data/protocols/demo.json"


def canonical(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(re.sub(r"[^\w]+", " ", "".join(
        char for char in folded if not unicodedata.combining(char)
    )).split())


class ProtocolCatalog:
    def __init__(self, path: Path = DEFAULT_CATALOG):
        self.document = CatalogFile.model_validate_json(path.read_text(encoding="utf-8"))
        if path == DEFAULT_CATALOG:
            general = CatalogFile.model_validate_json(
                path.with_name("general.json").read_text(encoding="utf-8"),
            )
            if any(protocol.scope != "general" for protocol in general.protocols):
                raise ValueError("El catálogo general solo admite guías generales.")
            self.document = CatalogFile(
                version="combined-demo-v1",
                source_file="data/protocols/demo.json + data/protocols/general.json",
                protocols=[*self.document.protocols, *general.protocols],
            )
            additions = FollowUpCatalog.model_validate_json(
                path.with_name("follow-ups.json").read_text(encoding="utf-8"),
            )
            by_text = {canonical(entry.question_text): entry.follow_up for entry in additions.entries}
            if len(by_text) != len(additions.entries):
                raise ValueError("Aclaraciones duplicadas para una misma pregunta.")
            for protocol in self.document.protocols:
                for question in protocol.questions:
                    question.follow_up = by_text.get(canonical(question.text))
        self.protocols = {protocol.id: protocol for protocol in self.document.protocols}
        self.general_by_category: dict[Category, ProtocolDefinition] = {}
        for protocol in self.protocols.values():
            if protocol.scope == "general":
                if protocol.category in self.general_by_category:
                    raise ValueError("Solo puede existir una guía general por categoría.")
                self.general_by_category[protocol.category] = protocol

    def general_for(self, category: Category) -> ProtocolDefinition | None:
        return self.general_by_category.get(category)

    def summaries(self, category: Category | None = None) -> list[ProtocolSummary]:
        return [protocol.summary() for protocol in self.protocols.values()
                if category is None or protocol.category == category]

    def get(self, protocol_id: str) -> ProtocolDefinition:
        try:
            return self.protocols[protocol_id]
        except KeyError:
            raise ProtocolError("protocol_not_found") from None
