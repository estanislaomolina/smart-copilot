import { test } from 'node:test';
import assert from 'node:assert/strict';
import { appendTurns, mergeReviewedData, compatibleProtocolId, nextGuidanceQuestion } from '../src/conversation.ts';

const unknown = () => ({ value: null, origin: 'unknown', evidence: [], rationale: null });
const manual = (value) => ({ value, origin: 'operator', evidence: [], rationale: 'Revisión manual.' });
const incident = () => ({
  category: unknown(), subcategory: unknown(), priority: unknown(), summary: unknown(),
  location: { street: unknown(), number: unknown(), intersection: unknown(), reference: unknown(), district: unknown() },
  risks: [], questions: [],
});

test('anexa turnos sin alterar el prefijo original ni aceptar turnos vacíos o exceso de longitud', () => {
  const original = '  Llamante: Hay humo 🏠.  ';
  assert.equal(appendTurns(original, ' ¿Hay gas? ', ' No. '),
    original + '\nOperador: ¿Hay gas?\nLlamante: No.');
  assert.equal(appendTurns(original, '', 'Sí.'), original + '\nLlamante: Sí.');
  assert.throws(() => appendTurns(original, ' ', ''), /Agregá/);
  assert.throws(() => appendTurns('x'.repeat(50000), '', 'Sí.'), /50.000/);
});

test('conserva decisiones humanas, incluidas opciones dejadas sin determinar, y avisa discrepancias', () => {
  const old = incident();
  old.category = manual('INCENDIO_RESCATE');
  old.priority = unknown();
  old.location.number = manual('1540');
  old.questions = [{ id: 'q', text: '¿Hay gas?', status: 'answered', answer: 'No.', origin: 'operator', evidence: [], rationale: null }];
  old.questions.push({ id: 'q2', text: '¿Hay heridos?', status: 'pending', answer: null,
    origin: 'operator', evidence: [], rationale: 'Reconfirmar.' });
  const fresh = incident();
  const extracted = value => ({ value, origin: 'transcript', evidence: [{ text: value, start: 0, end: value.length }], rationale: null });
  fresh.category = extracted('EMERGENCIA_MEDICA');
  fresh.priority = extracted('P1');
  fresh.location.number = extracted('1600');
  const { data, notices } = mergeReviewedData(fresh, old, ['priority']);
  assert.equal(data.category.value, 'INCENDIO_RESCATE');
  assert.equal(data.priority.value, null);
  assert.equal(data.location.number.value, '1540');
  assert.equal(data.questions[0].answer, 'No.');
  assert.equal(data.questions[1].status, 'pending');
  assert.equal(data.questions[1].origin, 'operator');
  assert.equal(notices.length, 3);
  data.questions[0].answer = 'Otro';
  assert.equal(old.questions[0].answer, 'No.');
});

test('conserva cada campo de ubicación revisado y el vaciado explícito ante una nueva extracción', () => {
  for (const key of Object.keys(incident().location)) {
    const old = incident(), fresh = incident();
    old.location[key] = manual('Valor revisado');
    fresh.location[key] = { value: 'Nueva sugerencia', origin: 'inference', evidence: [], rationale: 'Simulación' };
    const reviewed = mergeReviewedData(fresh, old, [`location.${key}`]);
    assert.deepEqual(reviewed.data.location[key], old.location[key]);
    assert.equal(reviewed.notices.length, 1);
    old.location[key] = unknown();
    const cleared = mergeReviewedData(fresh, old, [`location.${key}`]);
    assert.equal(cleared.data.location[key].value, null);
    assert.equal(cleared.notices.length, 1);
    assert.equal(mergeReviewedData(fresh, old, []).data.location[key].value, 'Nueva sugerencia');
  }
});

test('mantiene solo la elección explícita compatible de protocolo', () => {
  const data = incident(); data.category = manual('INCENDIO_RESCATE');
  const protocol = { selection: 'selected', protocol: { id: 'p', category: 'INCENDIO_RESCATE' } };
  assert.equal(compatibleProtocolId(protocol, data), 'p');
  data.category = manual('EMERGENCIA_MEDICA');
  assert.equal(compatibleProtocolId(protocol, data), undefined);
  protocol.selection = 'suggested';
  data.category = manual('INCENDIO_RESCATE');
  assert.equal(compatibleProtocolId(protocol, data), undefined);
});

test('la guía prioriza aclaraciones y avanza según estados sin depender del contenido', () => {
  const pending = { id: 'a', text: 'Dato aún no consultado', status: 'pending' };
  const ambiguous = { id: 'b', text: 'Dato que necesita revisión', status: 'ambiguous' };
  const clarification = { id: 'c', text: 'Otro asunto', status: 'ambiguous',
    follow_up: { id: 'follow', text: 'Aclaración del catálogo' } };
  const questions = [pending, ambiguous, clarification];
  assert.equal(nextGuidanceQuestion(questions), clarification);
  assert.equal(nextGuidanceQuestion([pending, ambiguous]), ambiguous);
  clarification.status = 'answered';
  assert.equal(nextGuidanceQuestion(questions), ambiguous);
  ambiguous.status = 'not_applicable';
  assert.equal(nextGuidanceQuestion(questions), pending);
  pending.status = 'answered';
  assert.equal(nextGuidanceQuestion(questions), null);
  assert.equal(nextGuidanceQuestion([]), null);
});
