import assert from 'node:assert/strict';
import { test } from 'node:test';

import { verifyUrl } from '../src/auth.mjs';
import { ConfigError, loadConfig } from '../src/config.mjs';
import { FIXTURE_DIR, GATEWAY_PROOF, postJson, startApp } from './helpers.mjs';

const CORTEX = { ASSISTANT_AUTH_MODE: 'cortex', CORTEX_APP_HEADER_SECRET: GATEWAY_PROOF };

test('config refuses dev auth without ASSISTANT_DEV=1 and cortex auth without the header secret', () => {
  assert.throws(() => loadConfig({ KNOWLEDGE_DIR: FIXTURE_DIR, ASSISTANT_AUTH_MODE: 'dev' }), ConfigError);
  assert.throws(() => loadConfig({ KNOWLEDGE_DIR: FIXTURE_DIR }), /CORTEX_APP_HEADER_SECRET/);
  assert.throws(
    () => loadConfig({ KNOWLEDGE_DIR: FIXTURE_DIR, ...CORTEX, CORTEX_APP_DIRECTORY_URL: 'https://c/api/v1/app-directory' }),
    /CORTEX_APP_KEY_FILE/,
  );
});

test('SSO lane: a missing or incorrect header secret is rejected', async () => {
  const app = await startApp({ env: CORTEX });
  const me = (headers) => fetch(`${app.url}/api/assistant/me`, { headers });
  try {
    assert.equal((await me({ 'x-cortex-email': 'anna@example.com' })).status, 401);
    assert.equal((await me({ 'x-cortex-email': 'anna@example.com', 'x-cortex-auth-secret': 'wrong' })).status, 401);
    assert.equal((await me({ 'x-cortex-email': 'anna@example.com', 'x-cortex-auth-secret': `${GATEWAY_PROOF}x` })).status, 401);
    const ok = await me({ 'x-cortex-email': 'Anna@Example.com', 'x-cortex-user': 'anna', 'x-cortex-auth-secret': GATEWAY_PROOF });
    assert.equal(ok.status, 200);
    assert.deepEqual((await ok.json()).user, { email: 'anna@example.com', name: 'anna' });
    assert.equal(ok.headers.get('x-content-type-options'), 'nosniff');
    assert.equal((await fetch(`${app.url}/api/health`)).status, 200);
    assert.equal((await postJson(`${app.url}/mcp`, { jsonrpc: '2.0', id: 1, method: 'ping' })).status, 401);
  } finally {
    await app.close();
  }
});

test('machine lane: cxu_ tokens are verified with the app key, cached, and reach /mcp and /api/agent only', async () => {
  const calls = [];
  const directory = async (url, init) => {
    calls.push({ url, authorization: init.headers.authorization, body: JSON.parse(init.body) });
    if (JSON.parse(init.body).token !== 'cxu_ok1') return new Response('{"error":"no"}', { status: 401 });
    return Response.json({
      tokenId: 't1',
      expiresAt: new Date(Date.now() + 86_400_000).toISOString(),
      user: { username: 'anna', email: 'anna@example.com', role: 'user', groups: [] },
    });
  };
  const app = await startApp({
    env: { ...CORTEX, CORTEX_APP_DIRECTORY_URL: 'https://control.test/api/v1/app-directory', CORTEX_APP_KEY_FILE: '/unused' },
    authOptions: { fetch: directory, readKey: () => 'cxk_app\n' },
  });
  const bearer = (token) => ({ authorization: `Bearer ${token}` });
  try {
    const ping = { jsonrpc: '2.0', id: 1, method: 'ping' };
    assert.equal((await postJson(`${app.url}/mcp`, ping, bearer('cxu_ok1'))).status, 200);
    assert.equal((await postJson(`${app.url}/mcp`, ping, bearer('cxu_ok1'))).status, 200);
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], {
      url: 'https://control.test/api/v1/app-directory/tokens/verify',
      authorization: 'Bearer cxk_app',
      body: { token: 'cxu_ok1' },
    });
    assert.equal((await postJson(`${app.url}/mcp`, ping, bearer('cxu_bad'))).status, 401);
    assert.equal(calls.length, 2);
    // A refused token is remembered: asking again makes no verify request.
    assert.equal((await postJson(`${app.url}/mcp`, ping, bearer('cxu_bad'))).status, 401);
    assert.equal(calls.length, 2);
    assert.equal((await postJson(`${app.url}/mcp`, ping, bearer('other'))).status, 401);

    const llms = await fetch(`${app.url}/api/agent/llms.txt`, { headers: bearer('cxu_ok1') });
    assert.equal(llms.status, 200);
    assert.match(await llms.text(), /Fixture llms\.txt/);
    assert.equal((await fetch(`${app.url}/api/agent/de/llms.txt`, { headers: bearer('cxu_ok1') })).status, 404);

    assert.equal((await fetch(`${app.url}/api/assistant/me`, { headers: bearer('cxu_ok1') })).status, 403);
  } finally {
    await app.close();
  }
});

test('the verify URL accepts the app-directory base or the Control origin', () => {
  assert.equal(verifyUrl('https://c/api/v1/app-directory'), 'https://c/api/v1/app-directory/tokens/verify');
  assert.equal(verifyUrl('https://c'), 'https://c/api/v1/app-directory/tokens/verify');
});
