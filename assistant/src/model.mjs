// The model through Cortex Keyring: the Anthropic Messages API, streamed. One `turn` is one
// `POST {base}/v1/messages` with `stream: true`; its Server-Sent Events become text pieces, complete
// tool calls and a final `done` with the assistant content. Keyring's refusals are typed errors, the
// caller's signal and a per-turn deadline abort the HTTP call, and no key or body is ever logged.

export const ANTHROPIC_VERSION = '2023-06-01';
const MESSAGES_PATH = '/v1/messages';

/** A model failure with the HTTP status and code the API reports for it. */
export class ModelError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** The typed failure for a Keyring status; never its body (Keyring echoes prompts). */
export function keyringRefusal(status) {
  switch (status) {
    case 401:
      return new ModelError(503, 'model_unavailable', 'Keyring refused the assistant’s key.');
    case 403:
      return new ModelError(503, 'model_unavailable', 'Keyring has no credential that may serve this model.');
    case 404:
      return new ModelError(503, 'model_unavailable', 'Keyring does not know this model.');
    case 429:
      return new ModelError(429, 'rate_limited', 'The model’s rate limit is reached for this minute. Try again shortly.');
    default:
      return new ModelError(503, 'model_unavailable', `The model could not be reached (Keyring answered ${status}).`);
  }
}

const UNAVAILABLE = (what) => new ModelError(503, 'model_unavailable', `The model ${what}. Try again later.`);

/**
 * Which key pays for this user's request (contract "Model access"). Returns `{key}` or `{error}`.
 * A subscriber key serves only its subscriber; everyone else needs the shared key.
 */
export function modelKeyFor(model, email) {
  if (model.baseUrl === '') return { error: new ModelError(503, 'model_unavailable', 'The assistant is not configured.') };
  if (model.subscriber !== '' && model.subscriberKey !== '' && email.toLowerCase() === model.subscriber) {
    return { key: model.subscriberKey };
  }
  if (model.sharedKey !== '') return { key: model.sharedKey };
  if (model.subscriber !== '') {
    return { error: new ModelError(403, 'assistant_unavailable', 'The assistant runs on the owner’s subscription.') };
  }
  return { error: new ModelError(503, 'model_unavailable', 'The assistant is not configured.') };
}

/** Matches the end of one SSE message: a blank line in any of the three newline spellings. */
const MESSAGE_END = /\r\n\r\n|\n\n|\r\r/;

/** Matches one line break in any of the three spellings. */
const LINE_BREAK = /\r\n|\n|\r/;

/** Upper bound of one unfinished SSE message, so a broken stream cannot grow memory without end. */
const MAX_PENDING_CHARS = 4 * 1024 * 1024;

/** Split a byte stream into Server-Sent Events `{event, data}` as they complete. */
export async function* sseMessages(body) {
  const decoder = new TextDecoder();
  let pending = '';
  for await (const chunk of body) {
    pending += decoder.decode(chunk, { stream: true });
    for (let end = MESSAGE_END.exec(pending); end !== null; end = MESSAGE_END.exec(pending)) {
      const block = pending.slice(0, end.index);
      pending = pending.slice(end.index + end[0].length);
      let event = 'message';
      const data = [];
      for (const line of block.split(LINE_BREAK)) {
        if (line.startsWith(':')) continue;
        const colon = line.indexOf(':');
        const field = colon === -1 ? line : line.slice(0, colon);
        const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, ''); // one optional leading space
        if (field === 'event') event = value;
        else if (field === 'data') data.push(value);
      }
      if (data.length > 0) yield { event, data: data.join('\n') };
    }
    if (pending.length > MAX_PENDING_CHARS) throw UNAVAILABLE('sent an oversized event');
  }
}

/** A tool call's input from its streamed JSON; `{}` when none, a marker when broken. */
function toolInput(json) {
  if (json.trim() === '') return {};
  try {
    return JSON.parse(json);
  } catch {
    return { unparsable: true };
  }
}

/**
 * @param options.baseUrl Keyring's Anthropic base URL
 * @param options.model the model id
 * @param options.fetch substitute for `fetch` (tests inject a fake transport here)
 */
export function createModelClient({ baseUrl, model, fetch: fetcher = globalThis.fetch }) {
  /**
   * One streamed turn. Yields `{type: 'text', text}`, `{type: 'tool_use', id, name, input}` and last
   * `{type: 'done', stopReason, content}` (the assistant content blocks for the next request).
   * Throws `ModelError`; `signal` aborts it (code `stopped`), as does the deadline (code
   * `model_unavailable`). `toolChoice` (e.g. `{type: 'none'}`) is sent as `tool_choice` when given.
   */
  async function* turn({ key, system, messages, tools, toolChoice, maxTokens, signal, timeoutMs }) {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    signal?.addEventListener('abort', abort);
    if (signal?.aborted) abort();
    const failure = () =>
      signal?.aborted
        ? new ModelError(499, 'stopped', 'The answer was stopped.')
        : timedOut
          ? new ModelError(504, 'model_unavailable', 'The model took too long to answer. Try again.')
          : null;
    try {
      let response;
      try {
        response = await fetcher(`${baseUrl}${MESSAGES_PATH}`, {
          method: 'POST',
          headers: { 'x-api-key': key, 'anthropic-version': ANTHROPIC_VERSION, 'content-type': 'application/json' },
          body: JSON.stringify({ model, max_tokens: maxTokens, stream: true, system, messages, tools, tool_choice: toolChoice }),
          signal: controller.signal,
          redirect: 'error',
        });
      } catch {
        throw failure() ?? UNAVAILABLE('could not be reached');
      }
      if (response.status >= 300) {
        await response.body?.cancel().catch(() => {});
        throw keyringRefusal(response.status);
      }
      if (response.body === null) throw UNAVAILABLE('answered without a stream');

      const blocks = [];
      let stopReason = 'end_turn';
      try {
        for await (const { data } of sseMessages(response.body)) {
          let frame;
          try {
            frame = JSON.parse(data);
          } catch {
            throw UNAVAILABLE('sent a frame that is not JSON');
          }
          switch (frame.type) {
            case 'content_block_start': {
              const block = frame.content_block ?? {};
              blocks[frame.index] = block.type === 'tool_use'
                ? { type: 'tool_use', id: block.id, name: block.name, json: '' }
                : block.type === 'text'
                  ? { type: 'text', text: '' }
                  : { type: 'other' };
              break;
            }
            case 'content_block_delta': {
              const block = blocks[frame.index];
              if (frame.delta?.type === 'text_delta' && block?.type === 'text') {
                block.text += frame.delta.text ?? '';
                yield { type: 'text', text: frame.delta.text ?? '' };
              } else if (frame.delta?.type === 'input_json_delta' && block?.type === 'tool_use') {
                block.json += frame.delta.partial_json ?? '';
              }
              break;
            }
            case 'content_block_stop': {
              const block = blocks[frame.index];
              if (block?.type === 'tool_use') {
                block.input = toolInput(block.json);
                yield { type: 'tool_use', id: block.id, name: block.name, input: block.input };
              }
              break;
            }
            case 'message_delta':
              stopReason = frame.delta?.stop_reason ?? stopReason;
              break;
            case 'message_stop': {
              const content = blocks
                .filter((block) => block !== undefined && block.type !== 'other')
                .filter((block) => block.type !== 'text' || block.text !== '')
                .map((block) => block.type === 'text'
                  ? { type: 'text', text: block.text }
                  : { type: 'tool_use', id: block.id, name: block.name, input: block.input ?? {} });
              yield { type: 'done', stopReason, content };
              return;
            }
            case 'error':
              throw frame.error?.type === 'overloaded_error'
                ? new ModelError(503, 'overloaded', 'The model is overloaded right now. Try again shortly.')
                : UNAVAILABLE(`reported ${frame.error?.type ?? 'an error'}`);
            default:
              break; // message_start, ping
          }
        }
      } catch (error) {
        throw failure() ?? (error instanceof ModelError ? error : UNAVAILABLE('stream broke off'));
      }
      throw failure() ?? UNAVAILABLE('stream ended early');
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
      controller.abort();
    }
  }

  return { model, turn };
}
