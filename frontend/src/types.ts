// Contratos públicos de backend/domain y backend/protocols.
export type Evidence = { text: string; start: number; end: number };
export type FieldValue = {
  value: string | null;
  origin: 'unknown' | 'transcript' | 'inference' | 'operator';
  evidence: Evidence[];
  rationale: string | null;
};
export type Question = {
  id: string; text: string;
  status: 'pending' | 'answered' | 'ambiguous' | 'not_applicable';
  answer: string | null; origin: 'transcript' | 'operator' | null;
  evidence: Evidence[]; rationale: string | null;
  follow_up?: { id: string; text: string; version: string; source: string; review_status: 'demo_unverified' } | null;
};
export type IncidentData = {
  location: Record<'street' | 'number' | 'intersection' | 'reference' | 'district', FieldValue>;
  category: FieldValue; subcategory: FieldValue; priority: FieldValue;
  risks: FieldValue[]; summary: FieldValue; questions: Question[];
};
export type ManualField = 'category' | 'priority' | `location.${keyof IncidentData['location']}`;
export type Analysis = {
  request: { transcript: string }; data: IncidentData;
  provider: 'mock' | 'real'; model: string | null; warnings: string[];
};
export type Protocol = {
  id: string; version: string; category: string; subcategory: string;
  scope: 'general' | 'specific';
  review_status: 'demo_unverified';
};
export type ProtocolResult = {
  selection: 'pending' | 'general' | 'suggested' | 'selected';
  protocol: Protocol | null; candidates: Protocol[]; questions: Question[];
  instructions: { id: string; text: string; source: string; review_status: string }[];
  warnings: string[];
  review_notices: string[];
};

export type CallStatus = 'draft' | 'reviewed' | 'referred';
export type CallContext = {
  analysis: Analysis | null; manual_mode: boolean; protocol: ProtocolResult | null;
  manual_fields: ManualField[];
  operator_turn: string; caller_turn: string;
  prepared_question: { id: string; protocol_id: string; prompt: string; number: number; stage: 'prepared' | 'awaiting_reply' } | null;
  question_update: { id: string; number: number } | null;
  update_notices: string[];
};
export type CallSnapshot = {
  request: Analysis['request']; data: IncidentData; operator_notes: string; context: CallContext;
};
export type StoredCall = {
  card: { id: string; revision: number; status: CallStatus; request: Analysis['request'];
    data: IncidentData; operator_notes: string; instructions: ProtocolResult['instructions'];
    created_at: string; reviewed_at: string | null; referred_at: string | null };
  context: CallContext; updated_at: string;
  referral: { id: string; mode: 'simulation'; destination: 'CAD simulado';
    reviewed_revision: number; created_at: string } | null;
};
export type CallSummary = {
  id: string; revision: number; status: CallStatus; updated_at: string;
  category: string | null; priority: string | null;
};
export type RevisionSummary = {
  revision: number; event: 'saved' | 'reviewed' | 'referred'; created_at: string;
};

export type ProviderInfo = { configured_provider: 'mock' | 'haiku' | 'groq'; configured_model: string | null };
