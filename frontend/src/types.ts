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
};
export type IncidentData = {
  location: Record<'street' | 'number' | 'intersection' | 'reference' | 'district', FieldValue>;
  category: FieldValue; subcategory: FieldValue; priority: FieldValue;
  risks: FieldValue[]; summary: FieldValue; questions: Question[];
};
export type Analysis = {
  request: { transcript: string }; data: IncidentData;
  provider: 'mock' | 'real'; model: string | null; warnings: string[];
};
export type Protocol = {
  id: string; version: string; category: string; subcategory: string;
  review_status: 'demo_unverified';
};
export type ProtocolResult = {
  selection: 'pending' | 'suggested' | 'selected';
  protocol: Protocol | null; candidates: Protocol[]; questions: Question[];
  instructions: { id: string; text: string; source: string; review_status: string }[];
  warnings: string[];
};
