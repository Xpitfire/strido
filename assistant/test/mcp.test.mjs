import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';

import { postJson, startApp } from './helpers.mjs';

let app;
let id = 0;
before(async () => {
  app = await startApp();
});
after(() => app.close());

async function rpc(method, params) {
  id += 1;
  const response = await postJson(`${app.url}/mcp`, { jsonrpc: '2.0', id, method, params });
  assert.equal(response.status, 200);
  return response.json();
}

test('initialize echoes a supported protocol version', async () => {
  const answer = await rpc('initialize', { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 't', version: '1' } });
  assert.equal(answer.result.protocolVersion, '2025-03-26');
  assert.deepEqual(answer.result.serverInfo, { name: 'strido', version: '1.0.0' });
  assert.deepEqual(answer.result.capabilities, { tools: {} });
  const unknown = await rpc('initialize', { protocolVersion: '1999-01-01' });
  assert.equal(unknown.result.protocolVersion, '2025-06-18');
});

test('notifications get 202, GET /mcp 405, broken JSON a parse error', async () => {
  const note = await postJson(`${app.url}/mcp`, { jsonrpc: '2.0', method: 'notifications/initialized' });
  assert.equal(note.status, 202);
  assert.equal((await fetch(`${app.url}/mcp`)).status, 405);
  const broken = await fetch(`${app.url}/mcp`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{' });
  assert.equal((await broken.json()).error.code, -32700);
  assert.equal((await rpc('nope')).error.code, -32601);
  assert.deepEqual((await rpc('ping')).result, {});
});

test('tools/list names the four tools with input schemas', async () => {
  const { result } = await rpc('tools/list');
  assert.deepEqual(result.tools.map((tool) => tool.name), ['search_docs', 'read_page', 'list_pages', 'search_parts']);
  for (const tool of result.tools) assert.equal(tool.inputSchema.type, 'object');
});

test('tools/call search_docs returns the fixture section with an absolute URL', async () => {
  const { result } = await rpc('tools/call', { name: 'search_docs', arguments: { query: 'main fuse servo branch' } });
  assert.equal(result.isError, false);
  const hits = JSON.parse(result.content[0].text);
  assert.equal(hits[0].url, 'https://strido.cortex.a2olabs.com/docs/electronics#ratings-and-why-these-parts');
  assert.equal(hits[0].section, 'Ratings and why these parts');

  const german = JSON.parse((await rpc('tools/call', { name: 'search_docs', arguments: { query: 'Hauptsicherung schutzt', language: 'de' } })).result.content[0].text);
  assert.equal(german[0].url, 'https://strido.cortex.a2olabs.com/de/docs/electronics#ratings-and-why-these-parts');
});

test('tools/call read_page, list_pages and search_parts', async () => {
  const page = (await rpc('tools/call', { name: 'read_page', arguments: { url_or_path: '/docs/electronics#ratings-and-why-these-parts' } })).result;
  assert.match(page.content[0].text, /25 A/);
  assert.match(page.content[0].text, /\[wiring check\]\(\/docs\/verification\/wiring#summary\)/);
  assert.match(page.content[0].text, /### Step 6 – Servo UBECs/);
  assert.doesNotMatch(page.content[0].text, /Safety rules/);
  assert.doesNotMatch(page.content[0].text, /PartsShop/);

  const step = (await rpc('tools/call', { name: 'read_page', arguments: { url_or_path: 'docs/electronics.md', section: 'step-6' } })).result;
  assert.match(step.content[0].text, /Two UBECs/);

  const pages = JSON.parse((await rpc('tools/call', { name: 'list_pages', arguments: {} })).result.content[0].text);
  assert.equal(pages[0].sections[0].items[0].url, 'https://strido.cortex.a2olabs.com/docs/electronics');

  const parts = JSON.parse((await rpc('tools/call', { name: 'search_parts', arguments: { query: 'fuse' } })).result.content[0].text);
  assert.deepEqual(
    { id: parts[0].id, price: parts[0].price, shop: parts[0].shop, url: parts[0].url },
    { id: 'fuse_25a', price: 0.36, shop: 'Reichelt.at', url: 'https://strido.cortex.a2olabs.com/docs/shop#part=fuse_25a' },
  );
});

test('bad tool input is an isError result', async () => {
  const missing = (await rpc('tools/call', { name: 'search_docs', arguments: {} })).result;
  assert.equal(missing.isError, true);
  assert.match(missing.content[0].text, /query is required/);
  const limit = (await rpc('tools/call', { name: 'search_docs', arguments: { query: 'x', limit: 50 } })).result;
  assert.equal(limit.isError, true);
  const page = (await rpc('tools/call', { name: 'read_page', arguments: { url_or_path: '/nope' } })).result;
  assert.equal(page.isError, true);
  assert.equal((await rpc('tools/call', { name: 'unknown_tool', arguments: {} })).error.code, -32602);
});
