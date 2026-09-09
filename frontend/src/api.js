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

/**
 * Ask a question, receiving the answer as it is produced.
 *
 * The server sends server-sent events: stage updates while it retrieves, the
 * citations as soon as retrieval finishes, then the answer token by token. That
 * ordering is the point — the sources appear roughly a second before the first
 * word of the answer, so the wait is never blank.
 *
 * EventSource cannot POST, so the frames are read off the fetch body and split
 * by hand. It is a few lines and avoids putting the question in a URL.
 */
export async function streamQuestion(question, onEvent) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/query/stream`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new Error("Could not reach the server. It may be starting up — try again in a moment.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed with status ${response.status}.`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Frames are separated by a blank line. The trailing piece may be a partial
    // frame, so it stays in the buffer until the rest of it arrives.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((candidate) => candidate.startsWith("data:"));
      if (line) onEvent(JSON.parse(line.slice(5).trim()));
    }
  }
}
