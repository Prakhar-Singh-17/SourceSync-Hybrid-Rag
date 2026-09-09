const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * One place that knows how to talk to the API.
 *
 * Every call needs the same three things: the base URL, `credentials: include`
 * so the session cookie travels cross-origin, and the server's `detail` message
 * surfaced as the error. Previously each of the six functions repeated all of
 * that by hand.
 */
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { credentials: "include", ...options });
  } catch {
    throw new Error("Could not reach the server. It may be starting up — try again in a moment.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed with status ${response.status}.`);
  }
  return response.json();
}

export const startSession = () => request("/api/session", { method: "POST" });

/** What this session has indexed. Read from the server so it survives a reload. */
export const getSession = () => request("/api/session");

export const clearSession = () => request("/api/session", { method: "DELETE" });

export const getApiHealth = () => request("/api/health");

export const getQdrantHealth = () => request("/api/health/qdrant");

export function ingestDocument(file) {
  const body = new FormData();
  body.append("upload", file);
  return request("/api/documents/ingest", { method: "POST", body });
}

export const ingestRepository = (url) =>
  request("/api/repositories/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

export const askQuestion = (question) =>
  request("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
