import type { StreamHandlers } from "./types";

/**
 * POST to {apiUrl}/chat and parse the Server-Sent Events stream.
 * Auth via X-API-Key. Mirrors the backend SSE contract:
 *   event: token | done | error  with JSON data.
 */
export async function sendChat(
  apiUrl: string,
  apiKey: string,
  message: string,
  sessionId: string,
  handlers: StreamHandlers,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${apiUrl.replace(/\/$/, "")}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
  } catch {
    handlers.onError("Network error. Please try again.");
    return;
  }

  if (!res.ok || !res.body) {
    const msg =
      res.status === 401
        ? "Authentication failed."
        : `Request failed (${res.status}).`;
    handlers.onError(msg);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "";
  let finished = false;

  const done = () => {
    if (finished) return;
    finished = true;
    handlers.onDone();
  };

  try {
    while (true) {
      const { done: streamDone, value } = await reader.read();
      if (streamDone) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.startsWith("event:")) {
          event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          const payload = line.slice(5).trim();
          if (!payload) continue;
          let data: any;
          try {
            data = JSON.parse(payload);
          } catch {
            continue;
          }
          if (event === "token") handlers.onToken(data.token ?? "");
          else if (event === "done") done();
          else if (event === "error") {
            handlers.onError(data.error ?? "Stream error.");
            finished = true;
            return;
          }
        }
      }
    }
  } catch {
    handlers.onError("Connection interrupted.");
    return;
  }
  done();
}
