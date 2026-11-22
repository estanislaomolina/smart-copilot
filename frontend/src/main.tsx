import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { analyze, applyProtocol, getProviderInfo } from './api';
import { appendTurns, compatibleProtocolId, mergeReviewedData, nextGuidanceQuestion } from './conversation';
import type { ManualField } from './conversation';
import type { Analysis, FieldValue, IncidentData, ProtocolResult, Question } from './types';
import { useCallPersistence } from './useCallPersistence';
import { CallCardDialog } from './CallCardDialog';
import type { CallSnapshot, StoredCall, ProviderInfo } from './types';
import './style.css';

const categories = {
  INCENDIO_RESCATE: 'Incendio y rescate', ACCIDENTE_VIAL: 'Accidente vial',
  EMERGENCIA_MEDICA: 'Emergencia médica', DEFENSA_CIVIL: 'Defensa civil',
  SERVICIOS_PUBLICOS: 'Servicios públicos', CONVIVENCIA_SEGURIDAD: 'Convivencia y seguridad',
};
const locationLabels = {
  street: 'Calle', number: 'Altura', intersection: 'Intersección',
  reference: 'Referencia', district: 'Localidad',
};
const originLabels = {
  unknown: 'Desconocido', transcript: 'Extraído del relato',
  inference: 'Inferencia por revisar', operator: 'Confirmado por operador',
};
const statusLabels = {
  pending: 'Pendiente', answered: 'Respondida', ambiguous: 'Ambigua', not_applicable: 'No aplica',
};
type PreparedQuestion = { id: string; protocolId: string; prompt: string; number: number; stage: 'prepared' | 'awaiting_reply' };
type QuestionUpdate = { id: string; number: number };

const unknown = (): FieldValue => ({ value: null, origin: 'unknown', evidence: [], rationale: null });
function EvidenceContent({ field }: { field: Pick<FieldValue, 'evidence' | 'rationale'> }) {
  return <div className="evidence-content">
    {field.evidence.map((span, index) => <blockquote key={index}>{span.text}</blockquote>)}
    {field.rationale && <p className="muted">{field.rationale}</p>}
  </div>;
}
function EvidenceView({ field }: { field: Pick<FieldValue, 'evidence' | 'rationale'> }) {
  if (!field.evidence.length && !field.rationale) return null;
  return <details className="evidence"><summary>{field.evidence.length ? 'Evidencia' : 'Criterio'}</summary><EvidenceContent field={field} /></details>;
}
function FieldView({ label, field }: { label?: string; field: FieldValue }) {
  const content = <>
    {label && <span className="field-label">{label}</span>}
    <strong>{field.value ?? 'Sin información'}</strong>
    <span className={'origin ' + field.origin} title={originLabels[field.origin]}>
      {{ unknown: 'Sin dato', transcript: 'Relato', inference: 'Inferido', operator: 'Operador' }[field.origin]}
    </span>
  </>;
  return field.evidence.length || field.rationale
    ? <details className="field-row"><summary title="Desplegar evidencia y criterio">{content}</summary>
        <EvidenceContent field={field} /></details>
    : <div className="field-row"><div className="field-summary">{content}</div></div>;
}
function ReviewField({ name, field, options, disabled, onReview }: {
  name: string; field: FieldValue; options: Record<string, string>; disabled: boolean;
  onReview: (value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  useEffect(() => { setEditing(false); }, [field]);
  return <div className="review-field">
    <span className="review-field-label">{name}</span>
    {editing ? <form className="review-field-editor" onSubmit={event => {
      event.preventDefault(); onReview(value); setEditing(false);
    }}>
      <select autoFocus id={name} aria-label={name} value={value} disabled={disabled}
        onChange={event => setValue(event.target.value)}>
        <option value="">Sin determinar</option>
        {Object.entries(options).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
      <div className="editor-actions">
        <button className="confirm-action" disabled={disabled}>
          {value && value === field.value ? 'Confirmar' : 'Guardar'}</button>
        <button className="text-action" type="button" disabled={disabled}
          onClick={() => setEditing(false)}>Cancelar</button>
      </div>
    </form> : <div className="review-field-value">
      <strong>{field.value ? options[field.value] ?? field.value : 'Sin definir'}</strong>
      <button className="text-action" aria-label={'Editar ' + name.toLowerCase()} disabled={disabled}
        onClick={() => { setValue(field.value ?? ''); setEditing(true); }}>Editar</button>
    </div>}
    <div className="field-meta">
      <span className={'origin ' + field.origin} title={originLabels[field.origin]}>
        {field.origin === 'operator' ? 'Revisado' : field.value ? 'Sugerido' : 'Sin información'}
      </span>
      <EvidenceView field={field} />
    </div>
  </div>;
}

function LocationField({ name, label, field, disabled, onReview }: {
  name: keyof IncidentData['location']; label: string; field: FieldValue;
  disabled: boolean; onReview: (value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  useEffect(() => { setEditing(false); }, [field]);
  return <div className="location-review" data-location={name}>
    <div className="location-review-row"><span className="field-label">{label}</span>
      <strong>{field.value ?? 'Sin información'}</strong>
      <span className={'origin ' + field.origin}>{field.origin === 'operator' ? 'Revisado'
        : field.value ? 'Sugerido' : 'Sin información'}</span>
      <EvidenceView field={field} />
      {!editing && <div className="location-actions">
        <button className="text-action" aria-label={'Editar ' + label.toLowerCase()} disabled={disabled}
          onClick={() => { setValue(field.value ?? ''); setEditing(true); }}>Editar</button>
      </div>}
    </div>
    {editing && <form className="location-editor" onSubmit={event => {
      event.preventDefault(); onReview(value.trim()); setEditing(false);
    }}>
      <label className="sr-only" htmlFor={'location-' + name}>{label}</label>
      <input autoFocus id={'location-' + name} value={value} disabled={disabled} maxLength={500}
        placeholder="Sin información" onChange={event => setValue(event.target.value)} />
      <button className="confirm-action" disabled={disabled}>
        {value.trim() && value.trim() === field.value ? 'Confirmar' : 'Guardar'}</button>
      <button className="text-action" type="button" disabled={disabled} onClick={() => setEditing(false)}>Cancelar</button>
      <small>Vacío: dejar sin información.</small>
    </form>}
  </div>;
}

function QuestionView({ question, disabled, onSave, number, prepared, waiting, updated }: {
  question: Question; number: number; prepared: boolean; waiting: boolean; updated: boolean; disabled: boolean; onSave: (question: Question) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState(question.status);
  const [answer, setAnswer] = useState(question.answer ?? '');
  const [reason, setReason] = useState(question.rationale ?? '');
  const [error, setError] = useState('');
  useEffect(() => {
    setStatus(question.status); setAnswer(question.answer ?? '');
    setReason(question.rationale ?? ''); setEditing(false); setError('');
  }, [question]);
  const needsReason = status === 'ambiguous' || status === 'not_applicable' || status === 'pending';
  async function save() {
    try {
      await onSave({ ...question, status, origin: 'operator', evidence: [],
        answer: status === 'pending' ? null : answer.trim() || null,
        rationale: reason.trim() || null });
      setEditing(false); setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo guardar la revisión.');
    }
  }
  return <article id={'checklist-' + question.id} data-question-id={question.id}
    className={'question' + (prepared ? ' question-prepared' : '') + (updated ? ' question-updated' : '')}>
    <div className="question-tracking"><span>Pregunta {number} · {question.origin === 'operator'
      ? 'Operador' : question.origin === 'transcript' ? 'Relato' : 'Sin respuesta'}</span>
      {prepared ? <strong>{waiting ? 'Preguntada · Esperando respuesta' : 'Preparada para preguntar'}</strong>
        : updated ? <strong>Actualizada con el último turno</strong>
        : question.status === 'ambiguous' ? <span>Requiere aclaración</span> : null}
      {!editing && <button className="text-action" disabled={disabled} onClick={() => setEditing(true)}>Revisar</button>}
    </div>
    <div><h4>{question.text}</h4>
      <select id={'state-' + question.id} aria-label={'Estado de ' + question.text} className={'question-state ' + question.status}
        value={editing ? status : question.status} disabled={disabled}
        onChange={event => { setStatus(event.target.value as Question['status']); setEditing(true); setError(''); }}>
        {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </div>
    {editing ? <form className="question-editor" onSubmit={event => { event.preventDefault(); void save(); }}>
      {status !== 'pending' && <><label htmlFor={'answer-' + question.id}>
        {status === 'answered' ? 'Respuesta registrada' : 'Respuesta (opcional)'}</label>
        <input id={'answer-' + question.id} value={answer} disabled={disabled}
          onChange={event => setAnswer(event.target.value)} required={status === 'answered'} /></>}
      <label htmlFor={'reason-' + question.id}>Justificación{needsReason ? '' : ' (opcional)'}</label>
      <input id={'reason-' + question.id} value={reason} disabled={disabled}
        onChange={event => setReason(event.target.value)} required={needsReason} />
      <div className="editor-actions"><button className="confirm-action" disabled={disabled
        || (status === 'answered' && !answer.trim()) || (needsReason && !reason.trim())}>Guardar revisión</button>
        <button type="button" className="text-action" disabled={disabled}
          onClick={() => { setEditing(false); setStatus(question.status); setAnswer(question.answer ?? '');
            setReason(question.rationale ?? ''); setError(''); }}>Cancelar</button></div>
      {error && <p className="error" role="alert">{error}</p>}
    </form> : <>
      {question.answer && <p>{question.answer}</p>}
      <EvidenceView field={question} />
    </>}
  </article>;
}

function App() {
  const [transcript, setTranscript] = useState('');
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [manualMode, setManualMode] = useState(false);
  const [providerInfo, setProviderInfo] = useState<ProviderInfo | null>(null);
  const [providerInfoError, setProviderInfoError] = useState(false);
  useEffect(() => {
    let current = true;
    void getProviderInfo().then(info => { if (current) setProviderInfo(info); })
      .catch(() => { if (current) setProviderInfoError(true); });
    return () => { current = false; };
  }, []);
  const [data, setData] = useState<IncidentData | null>(null);
  const transcriptInput = useRef<HTMLTextAreaElement>(null);
  const callerInput = useRef<HTMLTextAreaElement>(null);
  const [operatorTurn, setOperatorTurn] = useState('');
  const [callerTurn, setCallerTurn] = useState('');
  const [preparedQuestion, setPreparedQuestion] = useState<PreparedQuestion | null>(null);
  const [questionUpdate, setQuestionUpdate] = useState<QuestionUpdate | null>(null);
  const [manualFields, setManualFields] = useState<ManualField[]>([]);
  const [updateNotices, setUpdateNotices] = useState<string[]>([]);
  const updating = useRef(false);
  const [previousCallId, setPreviousCallId] = useState<string | null>(null);
  const [operatorNotes, setOperatorNotes] = useState('');
  const [cardOpen, setCardOpen] = useState(false);
  const [recoveryOpen, setRecoveryOpen] = useState(false);
  const recoveryDialog = useRef<HTMLDialogElement>(null);
  const [changingType, setChangingType] = useState(false);
  const [protocol, setProtocol] = useState<ProtocolResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [protocolError, setProtocolError] = useState('');
  const [protocolBusy, setProtocolBusy] = useState(false);

  async function loadProtocols(result: Pick<Analysis, 'request'>, nextData: IncidentData, id?: string, manual = manualMode) {
    setProtocolBusy(true); setProtocolError('');
    try {
      const next = await applyProtocol(result.request, nextData, id, manual);
      if (next.protocol?.id !== protocol?.protocol?.id) {
        setPreparedQuestion(null); setQuestionUpdate(null);
      }
      setProtocol(next); setChangingType(false);
      setData({ ...nextData, questions: next.questions });
    } catch (cause) {
      setProtocolError(cause instanceof Error ? cause.message : 'No se pudo obtener el protocolo.');
    } finally { setProtocolBusy(false); }
  }
  async function runAnalysis() {
    if (busy || protocolBusy || analysis || manualMode || !transcript.trim()) return;
    setBusy(true); setError('');
    try {
      const result = await analyze(transcript);
      const merged = data ? mergeReviewedData(result.data, data, manualFields) : null;
      const next = merged?.data ?? structuredClone(result.data);
      if (merged) setUpdateNotices(merged.notices);
      setAnalysis(result); setData(next); setProtocol(null); setPreviousCallId(null);
      await loadProtocols(result, next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo analizar la transcripción.');
    } finally { setBusy(false); }
  }
  async function addTurns() {
    if ((!analysis && !manualMode) || !data || busy || protocolBusy || updating.current) return;
    updating.current = true; setBusy(true); setError('');
    try {
      const nextTranscript = appendTurns(transcript, operatorTurn, callerTurn);
      const extracted = manualMode ? null : await analyze(nextTranscript);
      const request = { transcript: nextTranscript };
      const merged = extracted ? mergeReviewedData(extracted.data, { ...data, questions: protocol?.questions ?? [] }, manualFields)
        : { data: structuredClone(data), notices: [] };
      const id = compatibleProtocolId(protocol, merged.data);
      if (protocol?.selection === 'selected' && protocol.protocol && !id) {
        merged.notices.push('El protocolo anterior no coincide con la categoría actual. Elegí el tipo de incidente nuevamente.');
      }
      const nextProtocol = await applyProtocol(request, merged.data, id, manualMode);
      // Publicar la actualización solo si extracción y protocolo terminaron bien.
      setTranscript(nextTranscript); setAnalysis(extracted);
      setData({ ...merged.data, questions: nextProtocol.questions });
      setProtocol(nextProtocol); setProtocolError(''); setChangingType(false);
      setUpdateNotices(merged.notices);
      const linked = preparedQuestion && preparedQuestion.protocolId === nextProtocol.protocol?.id
        && (preparedQuestion.stage === 'awaiting_reply' ? !operatorTurn.trim()
          : preparedQuestion.prompt === operatorTurn) ? preparedQuestion : null;
      const updated = nextProtocol.questions.find(question => question.id === linked?.id);
      setQuestionUpdate(linked && updated
        ? { id: updated.id, number: linked.number } : null);
      setPreparedQuestion(linked && !callerTurn.trim() ? { ...linked, stage: 'awaiting_reply' } : null);
      setOperatorTurn(''); setCallerTurn('');
    } catch (cause) {
      setError('No se actualizó la llamada. ' + (cause instanceof Error ? cause.message : 'Reintentá la operación.'));
    } finally {
      updating.current = false; setBusy(false);
    }
  }
  async function saveQuestion(question: Question) {
    if ((!analysis && !manualMode) || !data || !protocol?.protocol || busy || protocolBusy) return;
    const nextData = { ...data, questions: protocol.questions.map(old => old.id === question.id ? question : old) };
    setProtocolBusy(true);
    try {
      const result = await applyProtocol({ transcript }, nextData, compatibleProtocolId(protocol, nextData), manualMode);
      setProtocol(result); setData({ ...nextData, questions: result.questions });
      if (questionUpdate?.id === question.id) setQuestionUpdate(null);
      if (preparedQuestion?.id === question.id) setPreparedQuestion(null);
    } finally { setProtocolBusy(false); }
  }
  function useQuestion(question: Question) {
    if (busy || protocolBusy) return;
    if (!protocol?.protocol) return;
    const prompt = question.follow_up?.text ?? question.text;
    setOperatorTurn(prompt);
    setPreparedQuestion({ id: question.id, protocolId: protocol.protocol.id, prompt,
      number: protocol.questions.findIndex(item => item.id === question.id) + 1, stage: 'prepared' });
    setQuestionUpdate(null);
    requestAnimationFrame(() => {
      callerInput.current?.focus();
      callerInput.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
  }
  function review(key: 'category' | 'priority', value: string) {
    if (!data || (!analysis && !manualMode)) return;
    const prior = data[key];
    const field: FieldValue = value
      ? { ...prior, value, origin: 'operator',
          evidence: value === prior.value ? prior.evidence : [],
          rationale: value === prior.value ? 'Dato confirmado individualmente por el operador.'
            : 'Dato corregido por el operador.' }
      : unknown();
    setManualFields(previous => [...new Set([...previous, key])]);
    const next = { ...data, [key]: field };
    const categoryChanged = key === 'category' && value !== (prior.value ?? '');
    if (categoryChanged) {
      next.subcategory = unknown(); next.questions = [];
      setProtocol(null); setChangingType(false);
    }
    setData(next);
    if (categoryChanged) void loadProtocols({ request: { transcript } }, next);
  }
  function reviewLocation(key: keyof IncidentData['location'], value: string) {
    if (!data || locked) return;
    const prior = data.location[key];
    const field: FieldValue = value
      ? { value, origin: 'operator', evidence: value === prior.value ? prior.evidence : [],
          rationale: value === prior.value ? 'Dato confirmado individualmente por el operador.'
            : 'Dato corregido por el operador.' }
      : unknown();
    setData({ ...data, location: { ...data.location, [key]: field } });
    setManualFields(previous => [...new Set<ManualField>([...previous, `location.${key}`])]);
  }
  async function newCall() {
    if (locked) return;
    try {
      const previous = await persistence.beginNew();
      setPreviousCallId(previous?.card.id ?? null);
      setPreparedQuestion(null); setQuestionUpdate(null);
      setOperatorTurn(''); setCallerTurn(''); setManualFields([]); setUpdateNotices([]);
      setTranscript(''); setAnalysis(null); setManualMode(false); setData(null); setProtocol(null); setOperatorNotes('');
      setChangingType(false); setError(''); setProtocolError('');
      requestAnimationFrame(() => transcriptInput.current?.focus());
    } catch { /* El error de guardado se muestra sin abandonar la llamada. */ }
  }
  async function restoreCall(id: string, discard = false) {
    try { await persistence.openCall(id, discard); setPreviousCallId(null); setRecoveryOpen(false); }
    catch { /* Conservar la llamada actual si no se pudo recuperar. */ }
  }
  function restore(item: StoredCall) {
    const context = item.context;
    setTranscript(item.card.request.transcript); setData(item.card.data);
    setAnalysis(context.analysis); setManualMode(context.manual_mode ?? false); setProtocol(context.protocol);
    setManualFields(context.manual_fields); setOperatorTurn(context.operator_turn);
    setCallerTurn(context.caller_turn); setUpdateNotices(context.update_notices);
    setQuestionUpdate(context.question_update); setOperatorNotes(item.card.operator_notes);
    const prepared = context.prepared_question;
    setPreparedQuestion(prepared ? { ...prepared, protocolId: prepared.protocol_id } : null);
    setChangingType(false); setError(''); setProtocolError('');
  }
  const reviewNotices = [...new Set([...updateNotices, ...(protocol?.review_notices ?? [])])];

  // Los tres paneles leen el mismo resultado confirmado por la API.
  // Los borradores de edición no reemplazan ese resultado hasta guardar.
  const checklistQuestions = protocol?.questions ?? [];
  const pendingQuestions = checklistQuestions.filter(question =>
    question.status === 'pending' || question.status === 'ambiguous');
  const pendingCount = pendingQuestions.length;
  const nextQuestion = nextGuidanceQuestion(checklistQuestions);
  const nextPrompt = nextQuestion?.follow_up?.text ?? nextQuestion?.text;
  const nextNumber = checklistQuestions.findIndex(question => question.id === nextQuestion?.id);
  const activePrepared = preparedQuestion?.protocolId === protocol?.protocol?.id
    && (preparedQuestion?.stage === 'awaiting_reply' ? !operatorTurn.trim()
      : preparedQuestion?.prompt === operatorTurn) ? preparedQuestion : null;
  const emptyData: IncidentData = {
    location: { street: unknown(), number: unknown(), intersection: unknown(), reference: unknown(), district: unknown() },
    category: unknown(), subcategory: unknown(), priority: unknown(), summary: unknown(), risks: [], questions: [],
  };
  const snapshot: CallSnapshot | null = transcript.trim() ? {
    request: { transcript }, data: { ...(data ?? emptyData), questions: checklistQuestions },
    operator_notes: operatorNotes,
    context: { analysis, manual_mode: manualMode, protocol, manual_fields: manualFields,
      operator_turn: operatorTurn, caller_turn: callerTurn,
      prepared_question: activePrepared ? { id: activePrepared.id, protocol_id: activePrepared.protocolId,
        prompt: activePrepared.prompt, number: activePrepared.number, stage: activePrepared.stage } : null,
      question_update: questionUpdate, update_notices: updateNotices },
  } : null;
  const persistence = useCallPersistence(snapshot, busy || protocolBusy, restore);
  const locked = busy || protocolBusy || persistence.booting || persistence.working;
  useEffect(() => {
    if (recoveryOpen) recoveryDialog.current?.showModal();
    else recoveryDialog.current?.close();
  }, [recoveryOpen]);
  function editSummary(value: string) {
    setData({ ...(data ?? emptyData), summary: value.trim()
      ? { value, origin: 'operator', evidence: [], rationale: 'Resumen redactado por el operador.' }
      : unknown() });
  }
  async function continueManually() {
    if (locked || !transcript.trim()) return;
    const next = data ?? emptyData;
    setManualMode(true); setData(next); setError('');
    await loadProtocols({ request: { transcript } }, next, compatibleProtocolId(protocol, next), true);
  }
  const reportedSignals = data?.risks.filter(risk => risk.origin === 'transcript' || risk.origin === 'operator') ?? [];
  const inferredRisks = data?.risks.filter(risk => risk.origin !== 'transcript' && risk.origin !== 'operator') ?? [];
  const clarificationQuestions = checklistQuestions.filter(question => question.status === 'ambiguous');
  const updatedQuestion = checklistQuestions.find(question => question.id === questionUpdate?.id);

  return <div className="app">
    <header>
      <div className="brand"><span className="brand-icon" aria-hidden="true">S</span>
        <strong>Smart Copilot</strong><span className="header-divider" aria-hidden="true" />
        <h1>Revisión de llamada</h1>
      </div>
      <div className="header-actions"><span className="badge">{manualMode ? 'Carga manual · Sin consultas IA'
        : providerInfo?.configured_provider === 'groq' ? 'Groq · ' + providerInfo.configured_model
        : providerInfo?.configured_provider === 'haiku' ? 'Anthropic · ' + providerInfo.configured_model
        : providerInfo ? 'Demo · Mock local' : providerInfoError ? 'Proveedor sin conexión' : 'Consultando proveedor…'}</span>
        <button className="secondary" disabled={locked || !transcript.trim()} onClick={() => setCardOpen(true)}>Revisar Carta de Llamada</button>
        <button className="secondary" disabled={locked} onClick={() => { void persistence.refresh(); setRecoveryOpen(true); }}>Recuperar llamada</button>
        <button className="secondary" onClick={() => void newCall()} disabled={locked || !transcript}>Nueva llamada</button>
      </div>
    </header>
    <main>
      <div className="notice"><strong>Prototipo.</strong> {manualMode ? 'Carga manual: completá los datos y el checklist.'
        : providerInfo?.configured_provider === 'mock' ? 'Revisá la prioridad: el mock puede omitir gravedad.'
        : providerInfo ? 'El modelo puede interpretar mal el relato. Revisá datos, riesgos y prioridad.'
        : 'Revisá datos, riesgos y prioridad.'}
        <span role="status"> {persistence.booting ? 'Recuperando llamada…' : persistence.saving ? 'Guardando…'
          : persistence.dirty ? 'Cambios sin guardar.' : persistence.current ? 'Guardada en SQLite · '
            + ({ draft: 'Borrador', reviewed: 'Revisada', referred: 'Derivada (simulación)' }[persistence.current.card.status])
            : 'Lista para una nueva llamada.'}</span>
      </div>
      {previousCallId && <div className="undo-notice" role="status">
        Espacio listo para otra llamada.
        <button className="text-action" disabled={locked} onClick={() => void restoreCall(previousCallId)}>Volver a la llamada anterior</button>
      </div>}
      {persistence.error && <div className="error save-error" role="alert">
        <span>{persistence.error}</span>
        {persistence.conflict ? <button className="secondary" disabled={locked}
          onClick={() => void restoreCall(persistence.callId, true)}>Descartar cambios locales y recuperar guardado</button>
          : <button className="secondary" disabled={locked || !snapshot}
            onClick={() => void persistence.saveNow().catch(() => undefined)}>Reintentar guardado</button>}
      </div>}
      {persistence.current?.card.status !== 'draft' && persistence.current && persistence.dirty &&
        <p className="notice">La llamada cambió: vuelve a borrador y requiere una nueva revisión antes de derivar.</p>}
      <div className="workspace" aria-busy={locked}>
        <section className="panel transcript-panel" aria-labelledby="transcript-title">
          <div className="section-title"><h2 id="transcript-title">1. Cargar llamada</h2><span>{manualMode ? 'Carga manual' : analysis ? 'Analizada' : 'Pegar y Enter'}</span></div>
          <label className="sr-only" htmlFor="transcript">Transcripción de la llamada</label>
          <textarea ref={transcriptInput} autoFocus id="transcript" maxLength={50000} value={transcript} readOnly={!!analysis || manualMode || locked}
            onChange={event => setTranscript(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && !event.repeat) {
                event.preventDefault();
                if (!locked && !analysis && !manualMode) void runAnalysis();
              }
            }}
            placeholder="Pegá el texto de la llamada…&#10;&#10;Operador: ¿Dónde ocurre?&#10;Llamante: …" />
          <div className="transcript-actions">
            <p className="muted">{analysis || manualMode
              ? 'Conversación completa. Podés continuar agregando turnos.'
              : 'Enter para analizar · Shift+Enter para otra línea.'}</p>
            {!analysis && !manualMode && <button className="primary" disabled={locked || !transcript.trim()} onClick={() => void runAnalysis()}>
              {busy ? 'Analizando…' : 'Analizar llamada'}
            </button>}
            {error && <p className="error" role="alert">{error}</p>}
            {!manualMode && (error || protocolError) && <button className="secondary" disabled={locked}
              onClick={() => void continueManually()}>Continuar con carga manual</button>}
            {(analysis || manualMode) && <form className="turn-form" onSubmit={event => {
              event.preventDefault(); void addTurns();
            }}>
              <h3>Continuar conversación</h3>
              <p className="muted">Simulación de transcripción progresiva.</p>
              {activePrepared && <p className="prepared-link" role="status">
                Pregunta {activePrepared.number} del checklist: {activePrepared.stage === 'awaiting_reply'
                  ? 'preguntada; esperando respuesta del ciudadano.' : 'preparada para preguntar.'}</p>}
              {questionUpdate && updatedQuestion && !activePrepared && <p className="question-update" role="status">
                Pregunta {questionUpdate.number}: {statusLabels[updatedQuestion.status].toLowerCase()}.
                {updatedQuestion.origin === 'operator' ? ' Se conserva la revisión manual.' : ' Ver respuesta y evidencia en el checklist.'}
              </p>}
              <label htmlFor="operator-turn">Operador</label>
              <input id="operator-turn" value={operatorTurn} disabled={locked} maxLength={50000}
                onChange={event => { setOperatorTurn(event.target.value); setPreparedQuestion(null); }} placeholder="Pregunta realizada (opcional)" />
              <label htmlFor="caller-turn">Ciudadano</label>
              <textarea ref={callerInput} id="caller-turn" value={callerTurn} disabled={locked} maxLength={50000} rows={2}
                onChange={event => setCallerTurn(event.target.value)} placeholder="Respuesta o información nueva"
                onKeyDown={event => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && !event.repeat) {
                    event.preventDefault();
                    if (!locked) event.currentTarget.form?.requestSubmit();
                  }
                }} />
              <button className="primary" disabled={locked || (!operatorTurn.trim() && !callerTurn.trim())}>
                {busy ? 'Actualizando…' : 'Agregar y actualizar análisis'}
              </button>
            </form>}
          </div>
        </section>

        <section className="panel incident-panel" aria-labelledby="incident-title">
          <div className="section-title"><h2 id="incident-title">2. Revisar datos</h2>
            <span>{data ? 'Por revisar' : 'Sin analizar'}</span></div>
          <div className="panel-body" tabIndex={0} role="region" aria-label="Datos y evidencia del incidente">
            {!data ? <div className="empty"><h3>Información de la llamada</h3>
              <p>Analizá el relato para revisar ubicación, categoría y prioridad.</p></div> : <>
              {!!reviewNotices.length && <div className="update-notices" role="status">
                <strong>Revisá los cambios</strong>
                {reviewNotices.map((notice, index) => <p key={index}>{notice}</p>)}
              </div>}
              <div className="review-grid">
                <ReviewField name="Categoría" field={data.category} options={categories} disabled={locked || (!analysis && !manualMode)}
                  onReview={value => review('category', value)} />
                <ReviewField name="Prioridad" field={data.priority} options={{ P1: 'P1', P2: 'P2', P3: 'P3', P4: 'P4' }} disabled={locked || (!analysis && !manualMode)}
                  onReview={value => review('priority', value)} />
              </div>
              <p className={'priority-summary ' + (data.priority.origin === 'operator' ? 'priority-confirmed'
                : data.priority.value ? 'priority-suggested' : 'priority-unknown')} role="status">
                {!data.priority.value ? 'Prioridad sin determinar'
                  : data.priority.origin === 'operator'
                    ? 'Prioridad confirmada por el operador: ' + data.priority.value
                    : 'Prioridad sugerida: ' + data.priority.value}
              </p>
              <h3>Ubicación</h3>
              <div className="location-fields">
                {Object.entries(locationLabels).map(([key, label]) => <LocationField key={key}
                  name={key as keyof typeof locationLabels} label={label}
                  field={data.location[key as keyof typeof locationLabels]} disabled={locked}
                  onReview={value => reviewLocation(key as keyof typeof locationLabels, value)} />)}
              </div>
              {!!reportedSignals.length && <>
                <div className="subsection-title"><h3>Información reportada</h3><span className="muted">Según el llamante</span></div>
                {reportedSignals.map((signal, index) => <FieldView key={index} field={signal} />)}
              </>}
              {!!clarificationQuestions.length && <div className="certainty-gaps">
                <h3>Por aclarar</h3>
                {clarificationQuestions.map(question => <p key={question.id} data-question-id={question.id}>
                  <strong>Pregunta {checklistQuestions.indexOf(question) + 1} · Requiere aclaración</strong>
                  <span>{question.text}</span>
                </p>)}
              </div>}
              <div className="subsection-title"><h3>Riesgos potenciales</h3><span className="muted">Inferidos · Revisar</span></div>
              <p className="muted risk-caption">La prioridad expresa gravedad sugerida; no confirma estos riesgos.</p>
              {inferredRisks.length ? inferredRisks.map((risk, index) => <FieldView key={index} field={risk} />)
                : <p className="muted">Sin riesgos inferidos reconocidos. No descarta peligro.</p>}
              {analysis?.warnings.some(warning => warning.startsWith('Análisis parcial:')) &&
                <p className="notice" role="status">Análisis parcial: algunos datos no pudieron validarse.
                  Revisá la información antes de continuar.</p>}
              <details className="source-details"><summary>Proveedor y limitaciones</summary>
                <p className="muted">{manualMode ? 'Carga manual; sin nueva interpretación automática' : analysis?.provider + ' · ' + analysis?.model}. Desplegá los datos para inspeccionar su evidencia.</p>
                {analysis?.warnings.map((warning, index) => <p className="muted" key={index}>{warning}</p>)}
              </details>
            </>}
          </div>
        </section>

        <section className="panel protocol-panel" aria-labelledby="protocol-title">
          <div className="section-title"><h2 id="protocol-title">3. Guiar la llamada</h2>
            <span>{protocol?.protocol ? `${pendingCount} por resolver` : 'Selección pendiente'}</span></div>
          <div className="panel-body" tabIndex={0} role="region" aria-label="Checklist e instrucciones">
            {!data ? <div className="empty"><h3>Preguntas e instrucciones</h3>
              <p>Acá vas a ver qué preguntar y qué indicar según el tipo de incidente.</p></div> : <>
              {protocolBusy && <p className="muted" role="status">Buscando protocolos…</p>}
              {protocolError && <div className="error" role="alert"><p>{protocolError}</p>
                <button className="secondary" disabled={locked} onClick={() => void loadProtocols({ request: { transcript } }, data)}>
                  Reintentar protocolos</button></div>}
              {protocol && <>
                {(!protocol.protocol || changingType) ? <fieldset className="incident-types" disabled={locked}>
                  <legend>Elegir guía o subtipo</legend>
                  <p className="muted">La guía general permite continuar. Podés elegir un subtipo si corresponde a la llamada.</p>
                  {!data.category.value && <p className="muted">Primero indicá la categoría en Revisar datos para acotar las opciones.</p>}
                  {protocol.candidates.map(candidate => <label className="type-option" key={candidate.id}>
                    <input type="radio" name="incident-type" value={candidate.id}
                      checked={protocol.protocol?.id === candidate.id}
                      onChange={() => {
                        void loadProtocols({ request: { transcript } }, data, candidate.id);
                      }} />
                    <span>{!data.category.value && <small>{categories[candidate.category as keyof typeof categories]} · </small>}
                      {candidate.subcategory}</span>
                  </label>)}
                  {protocol.protocol && <button className="text-action" onClick={() => setChangingType(false)}>Mantener guía actual</button>}
                </fieldset> : <div className="chosen-type">
                  <div><span className="label">{protocol.protocol.scope === 'general'
                    ? 'Guía general por categoría · Subtipo sin determinar' : 'Tipo de incidente'}</span>
                    <strong>{protocol.protocol.subcategory}</strong></div>
                  <button className="text-action" disabled={locked} onClick={() => setChangingType(true)}>{protocol.protocol.scope === 'general' ? 'Elegir subtipo (opcional)' : 'Cambiar'}</button>
                </div>}
                {protocol.protocol && <>
                  <div className="prearrival">
                    <div className="guidance-heading"><h3>DECIR AHORA</h3>
                      <span className="demo-label">Catálogo demo · Sin validar</span></div>
                    <p className="guidance-caption">Indicaciones para el ciudadano</p>
                    {protocol.instructions.length
                      ? <ul className="instructions">{protocol.instructions.map(instruction =>
                          <li key={instruction.id}>{instruction.text}</li>)}</ul>
                      : <p className="muted">Este protocolo no contiene instrucciones de prearribo.</p>}
                  </div>
                  {nextQuestion ? <div className="next-question">
                    <h3 className="next-label">PREGUNTAR DESPUÉS</h3>
                    <span className="question-reference">Seguimiento de la pregunta {nextNumber + 1} del checklist</span>
                    <p>{nextPrompt}</p>
                    <button className="primary" disabled={locked
                      || (activePrepared?.id === nextQuestion.id && activePrepared.stage === 'awaiting_reply')}
                      onClick={() => useQuestion(nextQuestion)}>
                      {activePrepared?.id === nextQuestion.id && activePrepared.stage === 'awaiting_reply'
                        ? 'Esperando respuesta del ciudadano'
                        : operatorTurn.trim() && operatorTurn !== nextPrompt
                          ? 'Reemplazar pregunta preparada' : 'Usar esta pregunta'}
                    </button>
                    {nextQuestion.status === 'ambiguous' && <div className="question-context">
                      <span className="muted">Ya informado · Requiere aclaración</span>
                      {nextQuestion.evidence.slice(-1).map((span, index) => <blockquote key={index}>{span.text}</blockquote>)}
                      {nextQuestion.follow_up && <span className="origin" title={nextQuestion.follow_up.source}>
                        Aclaración de catálogo · Demo sin validar</span>}
                    </div>}
                    {callerTurn.trim() && operatorTurn !== nextPrompt && <p className="muted">
                      Hay una respuesta sin enviar. Revisá que corresponda a esta pregunta.</p>}
                  </div> : <p className="checklist-complete" role="status">No quedan preguntas pendientes en este protocolo.</p>}
                  <div className="subsection-title"><h3>Checklist de atención</h3>
                    <span className="muted">{pendingCount} por resolver</span></div>
                  {checklistQuestions.map((question, index) =>
                    <QuestionView key={question.id} question={question} number={index + 1}
                      prepared={activePrepared?.id === question.id}
                      waiting={activePrepared?.id === question.id && activePrepared.stage === 'awaiting_reply'}
                      updated={questionUpdate?.id === question.id && activePrepared?.id !== question.id} disabled={locked} onSave={saveQuestion} />)}
                </>}
                <details className="source-details"><summary>Fuente y limitaciones del protocolo</summary>
                  <p className="muted">{protocol.protocol?.scope === 'general'
                    ? 'Guía general de curaduría propia para demostración. No confirma un subtipo ni está validada para uso operativo.'
                    : 'Catálogo sintético. Cada subtipo específico proviene de un único ejemplo; no es una clasificación operativa validada.'}</p>
                  {protocol.protocol && <p className="muted">{protocol.protocol.id} · {protocol.protocol.version} ·
                    {protocol.selection === 'selected' ? ' Seleccionado por operador' : ' Sugerido; revisar'}</p>}
                  {protocol.warnings.map((warning, index) => <p className="muted" key={index}>{warning}</p>)}
                  {protocol.instructions.map(instruction => <p className="muted" key={instruction.id}>{instruction.source}</p>)}
                  {protocol.questions.filter(question => question.follow_up).map(question =>
                    <p className="muted" key={question.id}>{question.follow_up?.version} · {question.follow_up?.source}</p>)}
                </details>
              </>}
            </>}
          </div>
        </section>
      </div>
    </main>
    <CallCardDialog open={cardOpen} snapshot={snapshot} stored={persistence.current}
      dirty={persistence.dirty} busy={locked} error={persistence.error}
      onClose={() => setCardOpen(false)} onSave={persistence.saveNow}
      onReview={() => persistence.transition('review')} onRefer={() => persistence.transition('refer')}
      onNotes={setOperatorNotes} onSummary={editSummary} />
    <dialog className="recovery-dialog" ref={recoveryDialog} onCancel={event => { event.preventDefault(); setRecoveryOpen(false); }}>
      <div className="card-dialog-heading"><h2>Recuperar llamada</h2>
        <button className="secondary" disabled={locked} onClick={() => setRecoveryOpen(false)}>Cerrar</button></div>
      <p className="muted">Últimas 50 llamadas guardadas en este servidor. Al abrir otra, primero se guarda la actual.</p>
      {persistence.error && <p className="error" role="alert">{persistence.error}</p>}
      {persistence.recent.length ? <ul className="call-list">{persistence.recent.map(call =>
        <li key={call.id}><button className="secondary" disabled={locked} onClick={() => void restoreCall(call.id)}>
          <strong>{categories[call.category as keyof typeof categories] ?? 'Sin categoría'} · {call.priority ?? 'Sin prioridad'}</strong>
          <span>{new Date(call.updated_at).toLocaleString()} · {{draft: 'Borrador', reviewed: 'Revisada', referred: 'Derivada (simulación)'}[call.status]}</span>
          <small>{call.id}</small>
        </button></li>)}</ul> : <p>No hay llamadas guardadas.</p>}
    </dialog>
  </div>;
}

createRoot(document.getElementById('root')!).render(<App />);
