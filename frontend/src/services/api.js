// Thin client for the FastAPI backend. All calls go through the Vite /api
// proxy in development (see vite.config.js) or VITE_API_BASE in production.

const BASE = import.meta.env.VITE_API_BASE || "";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError(
      "Can't reach the planning server. Start the backend on port 8000 and try again.",
      0,
    );
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep default */
    }
    throw new ApiError(detail, response.status);
  }
  return response.json();
}

export const api = {
  health: () => request("/api/health"),
  meta: () => request("/api/meta"),
  destinations: () => request("/api/destinations"),
  parseQuery: (query) =>
    request("/api/parse-query", { method: "POST", body: JSON.stringify({ query }) }),
  flights: (params) => request(`/api/flights?${new URLSearchParams(params)}`),
};

/**
 * Start a planning run and stream Server-Sent Events.
 * Uses fetch + ReadableStream because EventSource cannot POST a body.
 */
export async function streamPlan(tripRequest, { onEvent, signal, ruleBased = false }) {
  let response;
  try {
    response = await fetch(`${BASE}/api/plan/stream${ruleBased ? "?rule_based=true" : ""}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(tripRequest),
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(
      "Can't reach the planning server. Start the backend on port 8000 and try again.",
      0,
    );
  }
  if (!response.ok) {
    let detail = `Planning failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = chunk
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("");
      if (!data) continue;
      try {
        onEvent(JSON.parse(data));
      } catch {
        /* ignore malformed chunk */
      }
    }
  }
}
