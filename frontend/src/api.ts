import type { Analysis, IncidentData, ProtocolResult } from './types';

async function post<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: AbortSignal.timeout(20000),
    });
  } catch {
    throw new Error('La API no respondió o no se pudo conectar. Tus cambios siguen en pantalla.');
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.message ?? `La API devolvió un error (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export const analyze = (transcript: string) => post<Analysis>('/api/analyze', { transcript });
export const applyProtocol = (request: Analysis['request'], data: IncidentData, protocol_id?: string) =>
  post<ProtocolResult>('/api/protocols/apply', { request, data, protocol_id });
