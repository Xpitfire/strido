// HTTP client of the assistant service (same origin, behind the site's SSO): JSON calls and the
// streamed answer (POST returning text/event-stream, parsed from the response body).
import type { Locale } from '../i18n';

const API = '/api/assistant';
/** Longest single SSE event we buffer; a larger one means the stream is broken. */
const MAX_EVENT_CHARS = 1_000_000;

export interface Limits {
  maxPromptChars: number;
  maxAttachments: number;
  maxImageBytes: number;
  maxTextBytes: number;
}

export interface Me {
  user: { email: string; name: string };
  enabled: boolean;
  reason?: string;
  model: string;
  limits: Limits;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

export interface StoredAttachment {
  id: string;
  name: string;
  mediaType: string;
  size: number;
}

export interface Source {
  title: string;
  url: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  status: 'complete' | 'stopped' | 'error';
  attachments: StoredAttachment[];
  sources: Source[];
  createdAt: string;
}

export interface AttachmentUpload {
  name: string;
  mediaType: string;
  /** File bytes, base64. */
  data: string;
}

export interface SendBody {
  text: string;
  attachments: AttachmentUpload[];
  locale: Locale;
  page?: { path: string; title: string };
}

/** Answer context sent with every question (and with a regenerate request). */
export type AnswerContext = Pick<SendBody, 'locale' | 'page'>;

export interface StreamHandlers {
  conversation(conversation: Conversation): void;
  /** Not sent by regenerate (the question is already stored). */
  user?(message: Message): void;
  status(text: string): void;
  delta(text: string): void;
  done(message: Message): void;
}

/** A failed call: `status` is the HTTP status (0 for network, stream and client-side failures). */
export class AssistantError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
    message = code,
  ) {
    super(message);
    this.name = 'AssistantError';
  }
}

export function attachmentUrl(id: string): string {
  return `${API}/attachments/${encodeURIComponent(id)}`;
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: { accept: 'application/json', ...(init.body ? { 'content-type': 'application/json' } : {}) },
    });
  } catch (error) {
    if (init.signal?.aborted) throw new AssistantError('aborted', 0);
    throw new AssistantError('network', 0, String(error));
  }
  if (response.ok) return response;
  let code = `http_${response.status}`;
  let message = response.statusText;
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    code = body.error?.code ?? code;
    message = body.error?.message ?? message;
  } catch {
    // not JSON (a proxy page): the status alone describes the failure
  }
  throw new AssistantError(code, response.status, message);
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await call(path, init);
  // An expired SSO session answers with the sign-in page (HTML) instead of JSON.
  if (!response.headers.get('content-type')?.includes('application/json')) throw new AssistantError('bad_response', 0);
  return (await response.json()) as T;
}

const conversationPath = (id: string) => `/conversations/${encodeURIComponent(id)}`;

export const assistantApi = {
  me: () => json<Me>('/me'),
  conversations: async () => (await json<{ conversations: Conversation[] }>('/conversations')).conversations,
  rename: async (id: string, title: string) =>
    (await json<{ conversation: Conversation }>(conversationPath(id), { method: 'PATCH', body: JSON.stringify({ title }) })).conversation,
  remove: async (id: string) => {
    await call(conversationPath(id), { method: 'DELETE' });
  },
  messages: async (id: string) => (await json<{ messages: Message[] }>(`${conversationPath(id)}/messages`)).messages,
  /** Posts a question (`'new'` creates the conversation) and streams the answer. */
  send: (id: string, body: SendBody, handlers: StreamHandlers, signal: AbortSignal) =>
    stream(`${conversationPath(id)}/messages`, body, handlers, signal),
  /** Replaces the answer(s) after the conversation's last question with a new streamed one. */
  regenerate: (id: string, context: AnswerContext, handlers: StreamHandlers, signal: AbortSignal) =>
    stream(`${conversationPath(id)}/regenerate`, context, handlers, signal),
};

/**
 * POSTs `body` and feeds the streamed events to the handlers. Resolves after `done`; rejects with an
 * AssistantError (code `aborted` after `signal`).
 */
async function stream(path: string, body: object, handlers: StreamHandlers, signal: AbortSignal): Promise<void> {
  const response = await call(path, { method: 'POST', body: JSON.stringify(body), signal });
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new AssistantError('bad_response', 0);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      // CRLF line ends become LF (a CR at the very end waits for its LF in the next chunk).
      buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, '\n');
      let end: number;
      // Events are separated by one blank line.
      while ((end = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        if (dispatch(block, handlers)) return;
      }
      if (buffer.length > MAX_EVENT_CHARS) throw new AssistantError('bad_response', 0);
    }
  } catch (error) {
    if (signal.aborted) throw new AssistantError('aborted', 0);
    if (error instanceof AssistantError) throw error;
    throw new AssistantError('stream_ended', 0, String(error));
  } finally {
    reader.releaseLock();
  }
  throw new AssistantError(signal.aborted ? 'aborted' : 'stream_ended', 0);
}

/** Handles one SSE event block; true once the answer is complete. */
function dispatch(block: string, handlers: StreamHandlers): boolean {
  let event = 'message';
  const data: string[] = [];
  for (const line of block.split('\n')) {
    if (line.startsWith(':')) continue; // keep-alive comment
    const colon = line.indexOf(':');
    const field = colon < 0 ? line : line.slice(0, colon);
    const value = colon < 0 ? '' : line.slice(colon + (line[colon + 1] === ' ' ? 2 : 1));
    if (field === 'event') event = value;
    else if (field === 'data') data.push(value);
  }
  if (data.length === 0) return false;
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(data.join('\n')) as Record<string, unknown>;
  } catch {
    throw new AssistantError('bad_response', 0);
  }
  switch (event) {
    case 'conversation':
      handlers.conversation(payload.conversation as Conversation);
      return false;
    case 'user':
      handlers.user?.(payload.message as Message);
      return false;
    case 'status':
      handlers.status(String(payload.text ?? ''));
      return false;
    case 'delta':
      handlers.delta(String(payload.text ?? ''));
      return false;
    case 'done':
      handlers.done(payload.message as Message);
      return true;
    case 'error':
      throw new AssistantError(String(payload.code ?? 'failed'), 0, String(payload.message ?? ''));
    default:
      return false; // unknown events are ignored for forward compatibility
  }
}
