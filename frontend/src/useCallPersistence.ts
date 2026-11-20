import { useEffect, useRef, useState } from 'react';
import { ApiError, getCall, listCalls, saveCall, transitionCall } from './api';
import type { CallSnapshot, CallSummary, StoredCall } from './types';

const ACTIVE_KEY = 'smart-copilot-active-call';
const snapshotOf = (item: StoredCall): CallSnapshot => ({
  request: item.card.request, data: item.card.data,
  operator_notes: item.card.operator_notes, context: item.context,
});

/** Un solo escritor en esta pestaña; SQLite rechaza versiones ajenas. */
export function useCallPersistence(snapshot: CallSnapshot | null, paused: boolean,
  onRestore: (item: StoredCall) => void) {
  const [callId, setCallId] = useState<string>(() => crypto.randomUUID());
  const activeId = useRef(callId);
  const [current, setCurrent] = useState<StoredCall | null>(null);
  const [recent, setRecent] = useState<CallSummary[]>([]);
  const [booting, setBooting] = useState(true);
  const [saving, setSaving] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const versions = useRef(new Map<string, number>());
  const savedKeys = useRef(new Map<string, string>());
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const key = snapshot ? JSON.stringify(snapshot) : '';
  const dirty = !!snapshot && savedKeys.current.get(callId) !== key;

  function enqueue<T>(task: () => Promise<T>): Promise<T> {
    const result = queue.current.then(task, task);
    queue.current = result.then(() => undefined, () => undefined);
    return result;
  }
  function register(item: StoredCall, savedKey?: string) {
    const id = item.card.id;
    versions.current.set(id, item.card.revision);
    savedKeys.current.set(id, savedKey ?? JSON.stringify(snapshotOf(item)));
    setRecent(old => [{ id, revision: item.card.revision, status: item.card.status,
      updated_at: item.updated_at, category: item.card.data.category.value,
      priority: item.card.data.priority.value }, ...old.filter(entry => entry.id !== id)].slice(0, 50));
    if (activeId.current === id) setCurrent(item);
  }
  function failure(cause: unknown) {
    setError(cause instanceof Error ? cause.message : 'No se pudo guardar la llamada.');
    if (cause instanceof ApiError && cause.code === 'revision_conflict') setConflict(true);
  }
  async function saveNow(): Promise<StoredCall | null> {
    if (!snapshot) return null;
    const id = callId, captured = snapshot, capturedKey = key;
    setSaving(true);
    try {
      const item = await enqueue(async () => {
        const result = await saveCall(id, captured, versions.current.get(id) ?? 0);
        register(result, capturedKey);
        return result;
      });
      setError(''); setConflict(false);
      return item;
    } catch (cause) { failure(cause); throw cause; }
    finally { setSaving(false); }
  }
  async function activate(id: string) {
    const item = await getCall(id);
    activeId.current = id; setCallId(id);
    register(item); onRestore(item);
    localStorage.setItem(ACTIVE_KEY, id);
    setError(''); setConflict(false);
    return item;
  }
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const calls = await listCalls();
        if (cancelled) return;
        setRecent(calls);
        const storedId = localStorage.getItem(ACTIVE_KEY);
        const id = storedId === 'new' ? null : storedId ?? calls[0]?.id;
        if (id) {
          try { await activate(id); }
          catch (cause) {
            if (cause instanceof ApiError && cause.status === 404) localStorage.setItem(ACTIVE_KEY, 'new');
            else throw cause;
          }
        }
      } catch (cause) { if (!cancelled) failure(cause); }
      finally { if (!cancelled) setBooting(false); }
    })();
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (booting || paused || working || conflict || !snapshot || !dirty) return;
    const timer = window.setTimeout(() => { void saveNow().catch(() => undefined); }, 700);
    return () => window.clearTimeout(timer);
  }, [key, callId, paused, working, booting, conflict]);

  async function beginNew() {
    setWorking(true);
    try {
      const old = await saveNow();
      const id = crypto.randomUUID();
      activeId.current = id; setCallId(id); setCurrent(null);
      localStorage.setItem(ACTIVE_KEY, 'new');
      return old;
    } finally { setWorking(false); }
  }
  async function openCall(id: string, discardLocal = false) {
    setWorking(true);
    try {
      if (!discardLocal) await saveNow();
      await queue.current;
      return await activate(id);
    } catch (cause) { failure(cause); throw cause; }
    finally { setWorking(false); }
  }
  async function transition(action: 'review' | 'refer') {
    setWorking(true);
    try {
      const saved = await saveNow();
      if (!saved) throw new Error('Cargá una conversación antes de revisar.');
      const item = await enqueue(async () => {
        const result = await transitionCall(callId, action, versions.current.get(callId)!);
        register(result, key);
        return result;
      });
      setError(''); return item;
    } catch (cause) { failure(cause); throw cause; }
    finally { setWorking(false); }
  }
  // La referencia local guarda solo el UUID; los datos viven en SQLite.
  useEffect(() => {
    if (current?.card.id === callId) localStorage.setItem(ACTIVE_KEY, callId);
  }, [current, callId]);
  return { callId, current, recent, booting, saving, working, error, conflict, dirty,
    saveNow, beginNew, openCall, transition,
    refresh: async () => { try { setRecent(await listCalls()); } catch (cause) { failure(cause); } } };
}
