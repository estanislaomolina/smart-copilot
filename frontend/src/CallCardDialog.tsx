import { useEffect, useRef, useState } from 'react';
import { listRevisions } from './api';
import type { CallSnapshot, RevisionSummary, StoredCall } from './types';

const names: Record<string, string> = {
  INCENDIO_RESCATE: 'Incendio y rescate', ACCIDENTE_VIAL: 'Accidente vial',
  EMERGENCIA_MEDICA: 'Emergencia médica', DEFENSA_CIVIL: 'Defensa civil',
  SERVICIOS_PUBLICOS: 'Servicios públicos', CONVIVENCIA_SEGURIDAD: 'Convivencia y seguridad',
};
const statuses = { draft: 'Borrador', reviewed: 'Revisada', referred: 'Derivada · Simulación' };
const source = (origin: string) => ({
  operator: 'Operador', unknown: 'Sin información', transcript: 'Informado en el relato',
  inference: 'Inferido · Requiere revisión',
}[origin] ?? origin);

export function CallCardDialog({ open, snapshot, stored, dirty, busy, error, onClose, onSave,
  onReview, onRefer, onNotes, onSummary }: {
  open: boolean; snapshot: CallSnapshot | null; stored: StoredCall | null;
  dirty: boolean; busy: boolean; error: string; onClose: () => void;
  onSave: () => Promise<unknown>; onReview: () => Promise<unknown>; onRefer: () => Promise<unknown>;
  onNotes: (value: string) => void; onSummary: (value: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [history, setHistory] = useState<RevisionSummary[]>([]);
  const [historyError, setHistoryError] = useState('');
  const [actionError, setActionError] = useState('');
  const snapshotKey = JSON.stringify(snapshot);
  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal();
    if (!open && dialog.current?.open) dialog.current?.close();
  }, [open]);
  useEffect(() => { setAcknowledged(false); }, [snapshotKey]);
  useEffect(() => {
    if (!open || !stored) { setHistory([]); return; }
    let current = true; setHistoryError('');
    void listRevisions(stored.card.id).then(rows => { if (current) setHistory(rows); }).catch(() => { if (current) setHistoryError('No se pudo cargar el historial de versiones.'); });
    return () => { current = false; };
  }, [open, stored?.card.id, stored?.card.revision]);
  async function act(callback: () => Promise<unknown>) {
    setActionError('');
    try { await callback(); }
    catch (cause) { setActionError(cause instanceof Error ? cause.message : 'No se pudo completar la acción.'); }
  }
  const status = dirty ? 'draft' : stored?.card.status ?? 'draft';
  const pending = snapshot?.data.questions.filter(q => q.status === 'pending' || q.status === 'ambiguous') ?? [];
  const unsent = !!(snapshot?.context.operator_turn.trim() || snapshot?.context.caller_turn.trim());
  return <dialog className="card-dialog" ref={dialog} onCancel={event => { event.preventDefault(); onClose(); }}>
    <div className="card-dialog-heading"><div><h2>Carta de Llamada</h2>
      <span className="muted">{statuses[status]}{stored ? ' · Versión ' + stored.card.revision : ''}</span></div>
      <button className="secondary" onClick={onClose}>Cerrar</button></div>
    {snapshot && <div className="card-content">
      <div className="card-facts">
        <div><span>Categoría</span><strong>{names[snapshot.data.category.value ?? ''] ?? 'Sin determinar'}</strong>
          <small>{source(snapshot.data.category.origin)}</small></div>
        <div><span>Prioridad</span><strong>{snapshot.data.priority.value ?? 'Sin determinar'}</strong>
          <small>{snapshot.data.priority.origin === 'operator' ? 'Confirmada por operador' : 'Sin confirmar'}</small></div>
        <div><span>Subtipo / guía</span><strong>{snapshot.context.protocol?.protocol?.subcategory ?? 'Sin seleccionar'}</strong>
          <small>{snapshot.context.protocol?.protocol?.scope === 'general' ? 'Subtipo sin determinar' : 'Protocolo de demostración'}</small></div>
      </div>
      <h3>Ubicación</h3>
      <dl className="card-location">{Object.entries({
        street: 'Calle', number: 'Altura', intersection: 'Intersección', district: 'Localidad', reference: 'Referencia',
      }).map(([key, label]) => { const field = snapshot.data.location[key as keyof typeof snapshot.data.location];
        return <div key={key}><dt>{label}</dt><dd>{field.value ?? 'Sin información'} <small>({source(field.origin)})</small></dd></div>; })}</dl>
      <h3>Señales reportadas e inferidas</h3>
      {snapshot.data.risks.length ? <ul>{snapshot.data.risks.map((risk, index) =>
        <li key={index}>{risk.value} <small>({source(risk.origin)})</small></li>)}</ul> : <p className="muted">Sin señales reconocidas. No descarta riesgos.</p>}
      <label htmlFor="card-summary">Resumen de la situación · {source(snapshot.data.summary.origin)}</label>
      <textarea id="card-summary" value={snapshot.data.summary.value ?? ''} disabled={busy}
        maxLength={5000} onChange={event => onSummary(event.target.value)}
        placeholder="Podés redactar un resumen; no se generan hechos adicionales." />
      <h3>Información pendiente o ambigua ({pending.length})</h3>
      {pending.length ? <ul>{pending.map(q => <li key={q.id}>{q.text} · {q.status === 'ambiguous' ? 'Ambigua' : 'Pendiente'}</li>)}</ul>
        : <p className="muted">Sin preguntas pendientes en el protocolo aplicado.</p>}
      {!snapshot.context.protocol?.protocol && <p className="notice">Sin protocolo seleccionado; el checklist aún no está definido.</p>}
      <label htmlFor="card-notes">Observaciones del operador</label>
      <textarea id="card-notes" value={snapshot.operator_notes} disabled={busy} maxLength={10000}
        onChange={event => onNotes(event.target.value)} />
      <details><summary>Conversación completa y evidencia</summary><pre>{snapshot.request.transcript}</pre>
        {snapshot.data.questions.map(q => <div key={q.id}><strong>{q.text}</strong><p>{q.answer ?? 'Sin respuesta'}</p>
          {q.evidence.map((span, i) => <blockquote key={i}>{span.text}</blockquote>)}</div>)}
        {[snapshot.data.category, snapshot.data.priority, ...Object.values(snapshot.data.location), ...snapshot.data.risks, snapshot.data.summary]
          .filter(field => field.value).map((field, i) => <div key={i}><strong>{field.value} · {source(field.origin)}</strong>
            {field.evidence.map((span, j) => <blockquote key={j}>{span.text}</blockquote>)}
            {field.rationale && <p className="muted">{field.rationale}</p>}</div>)}</details>
      {historyError && <p className="error" role="alert">{historyError}</p>}
      {history.length > 0 && <details><summary>Historial de versiones ({history.length})</summary><ul>
        {history.map(row => <li key={row.revision}>Versión {row.revision} · {{
          saved: 'Guardado', reviewed: 'Revisión confirmada', referred: 'Derivación simulada',
        }[row.event]} · {new Date(row.created_at).toLocaleString()}</li>)}</ul></details>}
      {unsent && <p className="notice">Hay turnos sin incorporar. Actualizá la conversación o vaciá esos campos antes de confirmar la revisión.</p>}
      {status === 'draft' && <label className="review-ack"><input type="checkbox" checked={acknowledged}
        disabled={busy || unsent} onChange={event => setAcknowledged(event.target.checked)} />
        Revisé los datos, las sugerencias y la información pendiente. Entiendo que es una demostración.</label>}
      {stored?.referral && status === 'referred' && <div className="referral-receipt" role="status">
        <strong>Derivación simulada registrada</strong><p>{stored.referral.id}</p>
        <p>{new Date(stored.referral.created_at).toLocaleString()} · {stored.referral.destination}</p>
        <span>No se enviaron datos a un CAD real ni se despacharon recursos.</span>
      </div>}
      {(actionError || error) && <p className="error" role="alert">{actionError || error}</p>}
      <div className="card-actions">
        <button className="secondary" disabled={busy} onClick={() => void act(onSave)}>Guardar borrador</button>
        <button className="secondary" disabled={busy || status !== 'draft' || !acknowledged || unsent}
          onClick={() => void act(onReview)}>Confirmar revisión</button>
        <button className="primary" disabled={busy || status !== 'reviewed'} onClick={() => void act(onRefer)}>
          Derivar · Simulación</button>
      </div>
    </div>}
  </dialog>;
}
