const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function ensureSession() {
  const response = await fetch(`${API_BASE_URL}/api/session`, {
    credentials: "include",
    method: "POST",
  });
  if (!response.ok) throw new Error("Unable to start a temporary session.");
  return response.json();
}

export async function getApiHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health`, { credentials: "include" });
  if (!response.ok) throw new Error("The backend health check failed.");
  return response.json();
}

export async function getQdrantHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health/qdrant`, { credentials: "include" });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "The Qdrant health check failed.");
  }
  return response.json();
}

export async function ingestDocument(file) {
  const formData = new FormData();
  formData.append("upload", file);
  const response = await fetch(`${API_BASE_URL}/api/documents/ingest`, {
    body: formData,
    credentials: "include",
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "The document could not be indexed.");
  }
  return response.json();
}

export async function querySources(question) {
  const response = await fetch(`${API_BASE_URL}/api/query`, {
    body: JSON.stringify({ question }),
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "The question could not be answered.");
  }
  return response.json();
}

export async function validateRepository(url) {
  const response = await fetch(`${API_BASE_URL}/api/repositories/validate`, {
    body: JSON.stringify({ url }),
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "The repository could not be accepted.");
  }
  return response.json();
}

export async function ingestRepository(url) {
  const response = await fetch(`${API_BASE_URL}/api/repositories/ingest`, {
    body: JSON.stringify({ url }),
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "The repository could not be indexed.");
  }
  return response.json();
}
