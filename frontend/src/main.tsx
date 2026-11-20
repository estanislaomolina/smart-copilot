import { useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { analyze, applyProtocol } from './api';
import type { Analysis, FieldValue, IncidentData, ProtocolResult, Question } from './types';
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
  inference: 'Sugerencia del mock', operator: 'Confirmado por operador',
};
const statusLabels = {
  pending: 'Pendiente', answered: 'Respondida', ambiguous: 'Ambigua', not_applicable: 'No aplica',
};
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
      {{ unknown: 'Sin dato', transcript: 'Relato', inference: 'Mock', operator: 'Operador' }[field.origin]}
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
  return <div className="review-field"><label htmlFor={name}>{name}</label>
    <select id={name} value={field.value ?? ''} disabled={disabled} onChange={event => onReview(event.target.value)}>
      <option value="">{name === 'Prioridad' ? 'Sin dato' : 'Sin determinar'}</option>
      {Object.entries(options).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select>
    <div className="field-meta">
      <span className={'origin ' + field.origin} title={originLabels[field.origin]}>
        {{ unknown: 'Sin dato', transcript: 'Extraído', inference: 'Sugerido', operator: 'Confirmado' }[field.origin]}
      </span>
      <EvidenceView field={field} />
    </div>
  </div>;
}

function QuestionView({ question }: { question: Question }) {
  return <article className="question">
    <div><h4>{question.text}</h4><span className={'status ' + question.status}>{statusLabels[question.status]}</span></div>
    {question.answer && <p>{question.answer}</p>}
    {question.origin && <span className="origin">{question.origin === 'operator' ? 'Operador' : 'Respuesta del relato'}</span>}
    <EvidenceView field={question} />
  </article>;
}

function App() {
  const [transcript, setTranscript] = useState('');
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [data, setData] = useState<IncidentData | null>(null);
  const transcriptInput = useRef<HTMLTextAreaElement>(null);
  const [previousCall, setPreviousCall] = useState<{
    transcript: string; analysis: Analysis | null; data: IncidentData | null; protocol: ProtocolResult | null;
    error: string; protocolError: string;
  } | null>(null);
  const [changingType, setChangingType] = useState(false);
  const [protocol, setProtocol] = useState<ProtocolResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [protocolError, setProtocolError] = useState('');
  const [protocolBusy, setProtocolBusy] = useState(false);

  async function loadProtocols(result: Analysis, nextData: IncidentData, id?: string) {
    setProtocolBusy(true); setProtocolError('');
    try {
      const next = await applyProtocol(result.request, nextData, id);
      setProtocol(next); setChangingType(false);
      setData({ ...nextData, questions: next.questions });
    } catch (cause) {
      setProtocolError(cause instanceof Error ? cause.message : 'No se pudo obtener el protocolo.');
    } finally { setProtocolBusy(false); }
  }
  async function runAnalysis() {
    if (busy || protocolBusy || analysis || !transcript.trim()) return;
    setBusy(true); setError('');
    try {
      const result = await analyze(transcript);
      const next = structuredClone(result.data);
      setAnalysis(result); setData(next); setProtocol(null); setPreviousCall(null);
      await loadProtocols(result, next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo analizar la transcripción.');
    } finally { setBusy(false); }
  }
  function review(key: 'category' | 'priority', value: string) {
    if (!data || !analysis) return;
    const field: FieldValue = value
      ? { value, origin: 'operator', evidence: [], rationale: 'Confirmación o corrección manual en el panel.' }
      : unknown();
    const next = { ...data, [key]: field };
    if (key === 'category') {
      next.subcategory = unknown(); next.questions = [];
      setProtocol(null); setChangingType(false);
    }
    setData(next);
    if (key === 'category') void loadProtocols(analysis, next);
  }
  function confirmSuggestions() {
    if (!data) return;
    const next = { ...data };
    for (const key of ['category', 'priority'] as const) {
      if (data[key].value && data[key].origin !== 'operator') {
        next[key] = { value: data[key].value, origin: 'operator', evidence: [],
          rationale: 'Sugerencia confirmada por el operador en el panel.' };
      }
    }
    setData(next);
  }
  function newCall() {
    if (busy || protocolBusy) return;
    setPreviousCall({ transcript, analysis, data, protocol, error, protocolError });
    setTranscript(''); setAnalysis(null); setData(null); setProtocol(null);
    setChangingType(false); setError(''); setProtocolError('');
    requestAnimationFrame(() => transcriptInput.current?.focus());
  }
  function restorePreviousCall() {
    if (!previousCall || busy || protocolBusy) return;
    setTranscript(previousCall.transcript); setAnalysis(previousCall.analysis);
    setData(previousCall.data); setProtocol(previousCall.protocol);
    setError(previousCall.error); setProtocolError(previousCall.protocolError);
    setPreviousCall(null); setChangingType(false);
    requestAnimationFrame(() => transcriptInput.current?.focus());
  }
  const locked = busy || protocolBusy;

  const hasSuggestions = data && [data.category, data.priority].some(field =>
    field.value && field.origin !== 'operator');
  const pendingQuestions = protocol?.questions.filter(question =>
    question.status === 'pending' || question.status === 'ambiguous') ?? [];
  const resolvedQuestions = protocol?.questions.filter(question =>
    question.status === 'answered' || question.status === 'not_applicable') ?? [];
  const pendingCount = pendingQuestions.length;

  return <div className="app">
    <header>
      <div className="brand"><span className="brand-icon" aria-hidden="true">S</span>
        <strong>Smart Copilot</strong><span className="header-divider" aria-hidden="true" />
        <h1>Revisión de llamada</h1>
      </div>
      <div className="header-actions"><span className="badge">Demo · Mock local</span>
        <button className="secondary" onClick={newCall} disabled={locked || !transcript}>Nueva llamada</button>
      </div>
    </header>
    <main>
      <div className="notice"><strong>Demo local.</strong> Revisá la prioridad: el mock puede omitir gravedad.
        <span> Las llamadas todavía no se guardan al recargar.</span>
      </div>
      {previousCall && <div className="undo-notice" role="status">
        Espacio listo para otra llamada.
        <button className="text-action" disabled={locked} onClick={restorePreviousCall}>Volver a la llamada anterior</button>
      </div>}
      <div className="workspace" aria-busy={locked}>
        <section className="panel transcript-panel" aria-labelledby="transcript-title">
          <div className="section-title"><h2 id="transcript-title">1. Cargar llamada</h2><span>{analysis ? 'Analizada' : 'Pegar y Enter'}</span></div>
          <label className="sr-only" htmlFor="transcript">Transcripción de la llamada</label>
          <textarea ref={transcriptInput} autoFocus id="transcript" maxLength={50000} value={transcript} readOnly={!!analysis || busy}
            onChange={event => setTranscript(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && !event.repeat) {
                event.preventDefault();
                if (!locked && !analysis) void runAnalysis();
              }
            }}
            placeholder="Pegá el texto de la llamada…&#10;&#10;Operador: ¿Dónde ocurre?&#10;Llamante: …" />
          <div className="transcript-actions">
            <p className="muted">{analysis
              ? 'Análisis listo. Revisá los datos y las preguntas a la derecha.'
              : 'Enter para analizar · Shift+Enter para otra línea.'}</p>
            {!analysis && <button className="primary" disabled={locked || !transcript.trim()} onClick={() => void runAnalysis()}>
              {busy ? 'Analizando…' : 'Analizar llamada'}
            </button>}
            {error && <p className="error" role="alert">{error}</p>}
          </div>
        </section>

        <section className="panel incident-panel" aria-labelledby="incident-title">
          <div className="section-title"><h2 id="incident-title">2. Revisar datos</h2>
            <span>{data ? 'Por revisar' : 'Sin analizar'}</span></div>
          <div className="panel-body" tabIndex={0} role="region" aria-label="Datos y evidencia del incidente">
            {!data ? <div className="empty"><h3>Información de la llamada</h3>
              <p>Analizá el relato para revisar ubicación, categoría y prioridad.</p></div> : <>
              <div className="review-grid">
                <ReviewField name="Categoría" field={data.category} options={categories} disabled={locked}
                  onReview={value => review('category', value)} />
                <ReviewField name="Prioridad" field={data.priority} options={{ P1: 'P1', P2: 'P2', P3: 'P3', P4: 'P4' }} disabled={locked}
                  onReview={value => review('priority', value)} />
              </div>
              <div className="review-action">
                {hasSuggestions
                  ? <button className="confirm-action" disabled={locked} onClick={confirmSuggestions}>
                      Confirmar sugerencias
                    </button>
                  : <span className="muted">{[data.category, data.priority].every(field => field.origin === 'operator')
                      ? 'Categoría y prioridad confirmadas por operador.'
                      : 'Completá los datos que siguen sin determinar.'}</span>}
              </div>
              <h3>Ubicación</h3>
              <div className="location-fields">
                {Object.entries(locationLabels).map(([key, label]) => <FieldView key={key} label={label}
                  field={data.location[key as keyof typeof locationLabels]} />)}
              </div>
              <div className="subsection-title"><h3>Señales reconocidas</h3><span className="muted">Mock · Revisar</span></div>
              {data.risks.length ? data.risks.map((risk, index) => <FieldView key={index} field={risk} />)
                : <p className="muted">Sin señales reconocidas. No descarta riesgos.</p>}
              <details className="source-details"><summary>Proveedor y limitaciones</summary>
                <p className="muted">{analysis?.provider} · {analysis?.model}. Desplegá los datos para inspeccionar su evidencia.</p>
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
                <button className="secondary" disabled={locked} onClick={() => analysis && void loadProtocols(analysis, data)}>
                  Reintentar protocolos</button></div>}
              {protocol && <>
                {(!protocol.protocol || changingType) ? <fieldset className="incident-types" disabled={locked}>
                  <legend>¿Qué está ocurriendo?</legend>
                  <p className="muted">Elegí el tipo de incidente para ver las preguntas y las indicaciones correspondientes.</p>
                  {!data.category.value && <p className="muted">Primero indicá la categoría en Revisar datos para acotar las opciones.</p>}
                  {protocol.candidates.map(candidate => <label className="type-option" key={candidate.id}>
                    <input type="radio" name="incident-type" value={candidate.id}
                      checked={protocol.protocol?.id === candidate.id}
                      onChange={() => {
                        if (analysis) void loadProtocols(analysis, data, candidate.id);
                      }} />
                    <span>{!data.category.value && <small>{categories[candidate.category as keyof typeof categories]} · </small>}
                      {candidate.subcategory}</span>
                  </label>)}
                  {protocol.protocol && <button className="text-action" onClick={() => setChangingType(false)}>Mantener tipo actual</button>}
                </fieldset> : <div className="chosen-type">
                  <div><span className="label">Tipo de incidente</span><strong>{protocol.protocol.subcategory}</strong></div>
                  <button className="text-action" disabled={locked} onClick={() => setChangingType(true)}>Cambiar</button>
                </div>}
                {protocol.protocol && <>
                  <div className="subsection-title"><h3>Qué falta preguntar</h3><span className="muted">{pendingCount} pendientes</span></div>
                  {pendingQuestions.length
                    ? pendingQuestions.map(question => <QuestionView key={question.id} question={question} />)
                    : <p className="muted">No quedan preguntas pendientes en este protocolo.</p>}
                  {!!resolvedQuestions.length && <details className="source-details">
                    <summary>{resolvedQuestions.length} preguntas ya resueltas</summary>
                    {resolvedQuestions.map(question => <QuestionView key={question.id} question={question} />)}
                  </details>}
                  {!!protocol.instructions.length && <div className="prearrival">
                    <div className="subsection-title"><h3>Qué indicar al llamante</h3><span className="demo-label">Demo · Sin validar</span></div>
                    <ul className="instructions">{protocol.instructions.map(instruction => <li key={instruction.id}>{instruction.text}</li>)}</ul>
                  </div>}
                </>}
                <details className="source-details"><summary>Fuente y limitaciones del protocolo</summary>
                  <p className="muted">Catálogo sintético. Cada subtipo proviene de un único ejemplo; no es una clasificación operativa validada.</p>
                  {protocol.protocol && <p className="muted">{protocol.protocol.id} · {protocol.protocol.version} ·
                    {protocol.selection === 'selected' ? ' Seleccionado por operador' : ' Sugerido; revisar'}</p>}
                  {protocol.warnings.map((warning, index) => <p className="muted" key={index}>{warning}</p>)}
                  {protocol.instructions.map(instruction => <p className="muted" key={instruction.id}>{instruction.source}</p>)}
                </details>
              </>}
            </>}
          </div>
        </section>
      </div>
    </main>
  </div>;
}

createRoot(document.getElementById('root')!).render(<App />);
