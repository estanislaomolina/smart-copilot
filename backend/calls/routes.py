"""HTTP de persistencia y transiciones explícitas de la Carta de Llamada."""
from uuid import UUID
from fastapi import APIRouter

from backend.calls.models import (
    CallSummary, RevisionSummary, SaveCallRequest, StoredCall, TransitionRequest,
)
from backend.calls.store import CallStore


def call_routes(store: CallStore) -> APIRouter:
    router = APIRouter(prefix="/api/calls", tags=["calls"])

    @router.get("", response_model=list[CallSummary])
    def list_calls():
        return store.list_calls()

    @router.get("/{call_id}", response_model=StoredCall)
    def get_call(call_id: UUID):
        return store.get(call_id)

    @router.put("/{call_id}", response_model=StoredCall)
    def save_call(call_id: UUID, request: SaveCallRequest):
        return store.save(call_id, request.snapshot, request.expected_revision)

    @router.get("/{call_id}/revisions", response_model=list[RevisionSummary])
    def history(call_id: UUID):
        return store.history(call_id)

    @router.post("/{call_id}/review", response_model=StoredCall)
    def review(call_id: UUID, request: TransitionRequest):
        return store.transition(call_id, request.expected_revision, "review")

    @router.post("/{call_id}/refer", response_model=StoredCall)
    def refer(call_id: UUID, request: TransitionRequest):
        return store.transition(call_id, request.expected_revision, "refer")

    return router
