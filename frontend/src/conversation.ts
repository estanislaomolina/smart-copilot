import type { ManualField, FieldValue, IncidentData, ProtocolResult, Question } from './types';

export type { ManualField } from './types';

export function appendTurns(transcript: string, operator: string, caller: string): string {
  const turns = [
    operator.trim() ? `Operador: ${operator.trim()}` : '',
    caller.trim() ? `Llamante: ${caller.trim()}` : '',
  ].filter(Boolean);
  if (!turns.length) throw new Error('Agregá una pregunta o una respuesta para continuar.');
  // Solo anexar: los offsets existentes siguen apuntando al mismo texto.
  const next = transcript + '\n' + turns.join('\n');
  if (Array.from(next).length > 50000) throw new Error('La conversación supera el límite de 50.000 caracteres.');
  return next;
}

export function mergeReviewedData(
  extracted: IncidentData, previous: IncidentData, manualFields: ManualField[],
): { data: IncidentData; notices: string[] } {
  const data = structuredClone(extracted);
  const notices: string[] = [];
  const keep = (fresh: FieldValue, old: FieldValue, label: string, explicitlyCleared = false) => {
    if (old.origin !== 'operator' && !explicitlyCleared) return fresh;
    if (old.value !== fresh.value) {
      notices.push(`${label}: el análisis ahora sugiere ${fresh.value ?? 'sin información'}. Se conserva tu decisión: ${old.value ?? 'sin determinar'}.`);
    }
    return structuredClone(old);
  };
  for (const key of ['category', 'subcategory', 'priority', 'summary'] as const) {
    data[key] = keep(data[key], previous[key],
      { category: 'Categoría', subcategory: 'Subtipo', priority: 'Prioridad', summary: 'Resumen' }[key],
      manualFields.includes(key as ManualField));
  }
  for (const key of Object.keys(data.location) as (keyof IncidentData['location'])[]) {
    data.location[key] = keep(data.location[key], previous.location[key],
      { street: 'Calle', number: 'Altura', intersection: 'Intersección', reference: 'Referencia', district: 'Localidad' }[key],
      manualFields.includes(`location.${key}`));
  }
  const manualRisks = previous.risks.filter(risk => risk.origin === 'operator');
  data.risks = [...manualRisks, ...data.risks.filter(risk =>
    !manualRisks.some(old => old.value?.toLocaleLowerCase() === risk.value?.toLocaleLowerCase()))];
  // El motor recalcula respuestas automáticas y conserva las manuales compatibles.
  data.questions = structuredClone(previous.questions.filter(question => question.origin === 'operator'));
  return { data, notices };
}

export function compatibleProtocolId(protocol: ProtocolResult | null, data: IncidentData): string | undefined {
  return protocol?.selection === 'selected' && protocol.protocol
    && (!data.category.value || protocol.protocol.category === data.category.value)
    ? protocol.protocol.id : undefined;
}

/** Orden de atención demostrativo, independiente de categoría, texto e ID de llamada. */
export function nextGuidanceQuestion(questions: Question[]): Question | null {
  return questions.find(question => question.status === 'ambiguous' && question.follow_up)
    ?? questions.find(question => question.status === 'ambiguous')
    ?? questions.find(question => question.status === 'pending')
    ?? null;
}
