import assert from 'node:assert/strict';
import { test } from 'node:test';

import { loadConfig } from '../src/config.mjs';
import { createModelClient, keyringRefusal, modelKeyFor, sseMessages } from '../src/model.mjs';
import { FIXTURE_DIR, startApp } from './helpers.mjs';

const modelConfig = (env) =>
  loadConfig({ KNOWLEDGE_DIR: FIXTURE_DIR, ASSISTANT_AUTH_MODE: 'dev', ASSISTANT_DEV: '1', CORTEX_MODEL_BASE_URL: 'http://k', ...env }).model;

test('key choice: subscriber key only for the subscriber, shared key for the rest', () => {
  const both = modelConfig({ CORTEX_MODEL_SUBSCRIBER: 'Owner@Example.com', CORTEX_MODEL_SUBSCRIBER_KEY: 'sub', CORTEX_MODEL_KEY: 'shared' });
  assert.deepEqual(modelKeyFor(both, 'owner@example.com'), { key: 'sub' });
  assert.deepEqual(modelKeyFor(both, 'OWNER@example.com'), { key: 'sub' });
  assert.deepEqual(modelKeyFor(both, 'other@example.com'), { key: 'shared' });
});

test('key choice: subscriber without a shared key refuses everyone else with 403', () => {
  const only = modelConfig({ CORTEX_MODEL_SUBSCRIBER: 'owner@example.com', CORTEX_MODEL_SUBSCRIBER_KEY: 'sub', ANTHROPIC_AUTH_TOKEN: 'ignored' });
  assert.deepEqual(modelKeyFor(only, 'owner@example.com'), { key: 'sub' });
  const refused = modelKeyFor(only, 'other@example.com');
  assert.equal(refused.error.status, 403);
  assert.equal(refused.error.code, 'assistant_unavailable');
  assert.equal(refused.error.message, 'The assistant runs on the owner’s subscription.');
});

test('key choice: without a subscriber the first of CORTEX_MODEL_KEY, ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN', () => {
  assert.deepEqual(modelKeyFor(modelConfig({ ANTHROPIC_AUTH_TOKEN: 'token' }), 'a@x'), { key: 'token' });
  assert.deepEqual(modelKeyFor(modelConfig({ ANTHROPIC_API_KEY: 'api', ANTHROPIC_AUTH_TOKEN: 'token' }), 'a@x'), { key: 'api' });
  assert.deepEqual(modelKeyFor(modelConfig({ CORTEX_MODEL_KEY: 'c', ANTHROPIC_API_KEY: 'api' }), 'a@x'), { key: 'c' });
  const none = modelKeyFor(modelConfig({}), 'a@x');
  assert.equal(none.error.status, 503);
  const noBase = modelKeyFor(modelConfig({ CORTEX_MODEL_BASE_URL: '', CORTEX_MODEL_KEY: 'c' }), 'a@x');
  assert.equal(noBase.error.code, 'model_unavailable');
});

test('/me and the message route report the key choice', async () => {
  const app = await startApp({ env: { CORTEX_MODEL_KEY: '', CORTEX_MODEL_SUBSCRIBER: 'owner@example.com', CORTEX_MODEL_SUBSCRIBER_KEY: 'sub' } });
  try {
    const me = await (await fetch(`${app.url}/api/assistant/me`)).json();
    assert.equal(me.enabled, false);
    assert.equal(me.reason, 'The assistant runs on the owner’s subscription.');
    assert.equal(me.limits.maxImageBytes, 3_932_160);
    const refused = await fetch(`${app.url}/api/assistant/conversations/new/messages`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text: 'hi' }),
    });
    assert.equal(refused.status, 403);
    const health = await (await fetch(`${app.url}/api/health`)).json();
    assert.deepEqual(health, { ok: true, pages: { en: 3, de: 1 }, model: { configured: true } });
  } finally {
    await app.close();
  }
});

test('Keyring statuses become typed errors', () => {
  assert.equal(keyringRefusal(429).code, 'rate_limited');
  assert.equal(keyringRefusal(429).status, 429);
  for (const status of [401, 403, 404, 500, 502]) assert.equal(keyringRefusal(status).code, 'model_unavailable');
});

test('the SSE parser joins split chunks, skips comments and handles CRLF', async () => {
  const chunks = ['event: a\r\nda', 'ta: {"x":1}\r\n\r\n: comment\n\n', 'event: b\ndata: 2\n\n'];
  const body = ReadableStream.from(chunks.map((chunk) => new TextEncoder().encode(chunk)));
  const messages = [];
  for await (const message of sseMessages(body)) messages.push(message);
  assert.deepEqual(messages, [{ event: 'a', data: '{"x":1}' }, { event: 'b', data: '2' }]);
});

test('a stream that ends without message_stop is a model_unavailable error', async () => {
  const client = createModelClient({
    baseUrl: 'http://k',
    model: 'm',
    fetch: async () => new Response('event: message_start\ndata: {"type":"message_start","message":{}}\n\n'),
  });
  await assert.rejects(async () => {
    for await (const _ of client.turn({ key: 'k', system: '', messages: [], maxTokens: 1, timeoutMs: 1000 }));
  }, { code: 'model_unavailable' });
});
