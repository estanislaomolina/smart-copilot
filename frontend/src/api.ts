import type { Analysis, IncidentData, ProtocolResult, CallSnapshot, StoredCall, CallSummary, RevisionSummary, ProviderInfo } from './types';

export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) { super(message); }
}
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method, headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(path === '/api/analyze' || path === '/api/protocols/apply' ? 75000 : 20000),
    });
  } catch {
    throw new Error('La API no respondió o no se pudo conectar. Tus cambios siguen en pantalla.');
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(error?.message ?? `La API devolvió un error (${response.status}).`, response.status, error?.code);
  }
  return response.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) => request<T>(path, 'POST', body);

export const analyze = (transcript: string) => post<Analysis>('/api/analyze', { transcript });
export const applyProtocol = (request: Analysis['request'], data: IncidentData, protocol_id?: string, manual_only = false) =>
  post<ProtocolResult>('/api/protocols/apply', { request, data, protocol_id, manual_only });

export const listCalls = () => request<CallSummary[]>('/api/calls');
export const getCall = (id: string) => request<StoredCall>('/api/calls/' + id);
export const saveCall = (id: string, snapshot: CallSnapshot, expected_revision: number) =>
  request<StoredCall>('/api/calls/' + id, 'PUT', { snapshot, expected_revision });
export const listRevisions = (id: string) => request<RevisionSummary[]>('/api/calls/' + id + '/revisions');
export const transitionCall = (id: string, action: 'review' | 'refer', expected_revision: number) =>
  post<StoredCall>('/api/calls/' + id + '/' + action, { expected_revision, acknowledged: true });

export const getProviderInfo = () => request<ProviderInfo>('/api/config');
