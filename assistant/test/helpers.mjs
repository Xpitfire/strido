// Test scaffolding: the app on an ephemeral port over the fixture knowledge tree, an in-memory store,
// and a fake Keyring transport that streams scripted Messages API turns. No network.

import { fileURLToPath } from 'node:url';

import { createAuth } from '../src/auth.mjs';
import { loadConfig } from '../src/config.mjs';
import { Knowledge } from '../src/knowledge.mjs';
import { createModelClient } from '../src/model.mjs';
import { createApp } from '../src/server.mjs';
import { Store } from '../src/store.mjs';

export const FIXTURE_DIR = fileURLToPath(new URL('./fixtures/content', import.meta.url));
export const GATEWAY_PROOF = 'gateway-proof-for-tests';

const knowledge = new Knowledge(FIXTURE_DIR);

/** SSE frames of one scripted model turn: text pieces, then optional tool calls. */
export function turnFrames({ text = [], tools = [] } = {}) {
  const frames = [{ type: 'message_start', message: { usage: { input_tokens: 1 } } }];
  let index = 0;
  if (text.length > 0) {
    frames.push({ type: 'content_block_start', index, content_block: { type: 'text', text: '' } });
    for (const piece of text) frames.push({ type: 'content_block_delta', index, delta: { type: 'text_delta', text: piece } });
    frames.push({ type: 'content_block_stop', index });
    index += 1;
  }
  for (const tool of tools) {
    frames.push({ type: 'content_block_start', index, content_block: { type: 'tool_use', id: tool.id, name: tool.name, input: {} } });
    frames.push({ type: 'content_block_delta', index, delta: { type: 'input_json_delta', partial_json: JSON.stringify(tool.input) } });
    frames.push({ type: 'content_block_stop', index });
    index += 1;
  }
  frames.push({ type: 'message_delta', delta: { stop_reason: tools.length > 0 ? 'tool_use' : 'end_turn' }, usage: { output_tokens: 5 } });
  frames.push({ type: 'message_stop' });
  return frames;
}

function sse(frames) {
  return frames.map((frame) => `event: ${frame.type}\ndata: ${JSON.stringify(frame)}\n\n`).join('');
}

/**
 * A fake `fetch` for the model client. Each call takes the next turn: an array of frames, or
 * `{hang: frames}` which sends those frames and then waits until the request is aborted.
 * `requests` records the parsed request bodies and headers.
 */
export function fakeTransport(turns) {
  const requests = [];
  const fetch = async (url, init) => {
    requests.push({ url, headers: init.headers, body: JSON.parse(init.body) });
    const turn = turns.shift();
    if (turn === undefined) throw new Error('unexpected model call');
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        if (Array.isArray(turn)) {
          controller.enqueue(encoder.encode(sse(turn)));
          controller.close();
          return;
        }
        controller.enqueue(encoder.encode(sse(turn.hang)));
        init.signal.addEventListener('abort', () => controller.error(new DOMException('aborted', 'AbortError')));
      },
    });
    return new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } });
  };
  return { fetch, requests };
}

/** Start the app. Returns `{url, store, close}`. */
export async function startApp({ env = {}, fetch = fakeTransport([]).fetch, authOptions = {} } = {}) {
  const config = loadConfig({
    KNOWLEDGE_DIR: FIXTURE_DIR,
    ASSISTANT_AUTH_MODE: 'dev',
    ASSISTANT_DEV: '1',
    CORTEX_MODEL_BASE_URL: 'http://keyring.test',
    CORTEX_MODEL_KEY: 'shared-key',
    ...env,
  });
  const store = new Store(':memory:');
  const model = createModelClient({ baseUrl: config.model.baseUrl, model: config.model.id, fetch });
  const app = createApp({ config, knowledge, store, model, auth: createAuth(config.auth, authOptions) });
  await new Promise((resolve) => app.server.listen(0, '127.0.0.1', resolve));
  const { port } = app.server.address();
  return {
    url: `http://127.0.0.1:${port}`,
    store,
    close: async () => {
      await app.close();
      store.close();
    },
  };
}

/** Parse an SSE body into `[{event, data}]` (comments skipped). */
export function parseEvents(text) {
  return text
    .split('\n\n')
    .filter((block) => block.trim() !== '' && !block.startsWith(':'))
    .map((block) => {
      const event = /^event: (.*)$/m.exec(block)?.[1]; // the event name line
      const data = /^data: (.*)$/m.exec(block)?.[1]; // the (single-line JSON) data line
      return { event, data: JSON.parse(data) };
    });
}

export function postJson(url, body, headers = {}) {
  return fetch(url, { method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: JSON.stringify(body) });
}
