const DB_NAME = "atlas-cache";
const DB_VERSION = 1;
const STORE_NAME = "data";

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE_NAME, { keyPath: "url" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error("cache timeout")), ms);
    promise.then(
      (value) => {
        window.clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        window.clearTimeout(timer);
        reject(error);
      },
    );
  });
}

export async function cachedFetch<T>(url: string, ttlMs = 5 * 60 * 1000): Promise<T> {
  try {
    const db = await withTimeout(openDB(), 750);
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const existing = await withTimeout(new Promise<{ url: string; data: T; ts: number } | undefined>(
      (resolve, reject) => {
        const req = store.get(url);
        req.onsuccess = () => resolve(req.result ?? undefined);
        req.onerror = () => reject(req.error);
      },
    ), 750);
    if (existing && Date.now() - existing.ts < ttlMs) {
      db.close();
      return existing.data;
    }
    db.close();
  } catch {
    // cache miss or unavailable — fetch from network
  }

  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}${resp.status === 404 ? " - file not found" : ""}`);
  const data: T = await resp.json();

  try {
    const db = await withTimeout(openDB(), 750);
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    store.put({ url, data, ts: Date.now() });
    await withTimeout(new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    }), 750);
    db.close();
  } catch {
    // cache write failure is non-fatal
  }

  return data;
}
