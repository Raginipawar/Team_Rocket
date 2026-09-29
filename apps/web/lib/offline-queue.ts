"use client";

// Paramedic offline queue (technical.md §11.12): mutations made without a connection
// are stored in IndexedDB with their Idempotency-Key and replayed in order when the
// connection comes back. The same key means the server applies each action once.

type Item = { id?: number; path: string; method: string; body: unknown; key: string; at: number };

const DB = "goldenhour";
const STORE = "outbox";
const listeners = new Set<(n: number) => void>();

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const r = fn(t.objectStore(STORE));
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}

export async function enqueue(item: Omit<Item, "at" | "id">) {
  await tx("readwrite", (s) => s.add({ ...item, at: Date.now() }));
  notify();
}

export async function pending(): Promise<Item[]> {
  if (typeof indexedDB === "undefined") return [];
  return tx("readonly", (s) => s.getAll() as IDBRequest<Item[]>);
}

async function remove(id: number) {
  await tx("readwrite", (s) => s.delete(id));
}

async function notify() {
  const n = (await pending()).length;
  listeners.forEach((l) => l(n));
}

export function onQueueChange(fn: (n: number) => void) {
  listeners.add(fn);
  void notify();
  return () => listeners.delete(fn);
}

let flushing = false;
/** Replays queued actions in order. Stops at the first network failure. */
export async function flush(token: () => string | null) {
  if (flushing) return;
  flushing = true;
  try {
    for (const item of await pending()) {
      try {
        const res = await fetch(`/api/v1${item.path}`, {
          method: item.method,
          headers: { "content-type": "application/json", "idempotency-key": item.key, ...(token() ? { authorization: `Bearer ${token()}` } : {}) },
          body: item.body === null ? undefined : JSON.stringify(item.body),
        });
        // 2xx applied, 4xx will never succeed (e.g. already done): drop either way
        if (res.status < 500) await remove(item.id!);
        else break;
      } catch {
        break;
      }
    }
  } finally {
    flushing = false;
    void notify();
  }
}
