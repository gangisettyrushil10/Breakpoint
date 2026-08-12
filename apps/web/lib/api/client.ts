import type { SimulateRequest, SimulateResponse } from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function simulate(
  request: SimulateRequest,
  options: { signal?: AbortSignal } = {}
): Promise<SimulateResponse> {
  const response = await fetch(`${API_URL}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: options.signal,
  });

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      typeof body === "object" && body && "detail" in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(`Simulate failed: ${detail}`, response.status, body);
  }

  return body as SimulateResponse;
}

export async function healthCheck(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

export { API_URL };
