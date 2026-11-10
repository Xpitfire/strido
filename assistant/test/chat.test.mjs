import assert from 'node:assert/strict';
import { setTimeout as delay } from 'node:timers/promises';
import { test } from 'node:test';

import { buildHistory } from '../src/chat.mjs';
import { fakeTransport, parseEvents, postJson, startApp, turnFrames } from './helpers.mjs';

const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0]);

test('a message streams conversation, user, status, delta, done and is stored with sources', async () => {
  const transport = fakeTransport([
    turnFrames({ tools: [{ id: 'tool_1', name: 'search_docs', input: { query: 'main fuse servo' } }] }),
    turnFrames({ text: ['The main fuse is **25 A** ', '([ratings](/docs/electronics#ratings-and-why-these-parts)).'] }),
  ]);
  const app = await startApp({ fetch: transport.fetch });
  try {
    const response = await postJson(`${app.url}/api/assistant/conversations/new/messages`, {
      text: 'Which fuse protects the servo branch?',
      locale: 'en',
      page: { path: '/docs/electronics', title: 'Electronics' },
    });
    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type'), /^text\/event-stream/);
    assert.equal(response.headers.get('x-accel-buffering'), 'no');
    const events = parseEvents(await response.text());
    assert.deepEqual(events.map((e) => e.event), ['conversation', 'user', 'status', 'delta', 'delta', 'done']);

    const [conversation, user, status] = events;
    assert.equal(conversation.data.conversation.title, 'Which fuse protects the servo branch?');
    assert.equal(user.data.message.role, 'user');
    assert.equal(status.data.text, 'Searching the docs: main fuse servo');
    const done = events.at(-1).data.message;
    assert.equal(done.status, 'complete');
    assert.equal(done.text, 'The main fuse is **25 A** ([ratings](/docs/electronics#ratings-and-why-these-parts)).');
    assert.deepEqual(done.sources, [
      { title: 'Electronics, wiring and power – Ratings and why these parts', url: '/docs/electronics#ratings-and-why-these-parts' },
    ]);

    // The tool ran against the knowledge base and its result went back to the model.
    const second = transport.requests[1].body;
    const toolResult = second.messages.at(-1).content[0];
    assert.equal(toolResult.type, 'tool_result');
    assert.match(toolResult.content, /ratings-and-why-these-parts/);
    assert.match(second.system, /\/docs\/electronics/);
    assert.equal(second.max_tokens, 4096);
    assert.equal(transport.requests[0].headers['x-api-key'], 'shared-key');

    const stored = app.store.listMessages('dev@localhost', conversation.data.conversation.id);
    assert.deepEqual(stored.map((m) => [m.role, m.status]), [['user', 'complete'], ['assistant', 'complete']]);
  } finally {
    await app.close();
  }
});

test('closing the request stops the model call and stores the partial answer as stopped', async () => {
  const transport = fakeTransport([{ hang: turnFrames({ text: ['Partial answer'] }).slice(0, 3) }]);
  const app = await startApp({ fetch: transport.fetch });
  try {
    const response = await postJson(`${app.url}/api/assistant/conversations/new/messages`, { text: 'Long question' });
    const reader = response.body.getReader();
    let seen = '';
    while (!seen.includes('event: delta')) seen += new TextDecoder().decode((await reader.read()).value);
    await reader.cancel();

    let messages = [];
    for (let attempt = 0; attempt < 50 && messages.length < 2; attempt += 1) {
      await delay(20);
      const [conversation] = app.store.listConversations('dev@localhost');
      messages = app.store.listMessages('dev@localhost', conversation.id);
    }
    assert.equal(messages.length, 2);
    assert.equal(messages[1].status, 'stopped');
    assert.equal(messages[1].text, 'Partial answer');
  } finally {
    await app.close();
  }
});

test('a model refusal emits an error event and stores the answer with status error', async () => {
  const app = await startApp({ fetch: async () => new Response('limit', { status: 429 }) });
  try {
    const response = await postJson(`${app.url}/api/assistant/conversations/new/messages`, { text: 'Hi' });
    const events = parseEvents(await response.text());
    assert.deepEqual(events.map((e) => e.event), ['conversation', 'user', 'error']);
    assert.equal(events[2].data.code, 'rate_limited');
    const [conversation] = app.store.listConversations('dev@localhost');
    assert.equal(app.store.listMessages('dev@localhost', conversation.id)[1].status, 'error');
  } finally {
    await app.close();
  }
});

test('attachments: oversized image 413, wrong magic bytes 415, empty message 400', async () => {
  const app = await startApp();
  const send = (body) => postJson(`${app.url}/api/assistant/conversations/new/messages`, body);
  try {
    const big = Buffer.concat([PNG, Buffer.alloc(4 * 1024 * 1024)]).toString('base64');
    const oversized = await send({ text: 'x', attachments: [{ name: 'big.png', mediaType: 'image/png', data: big }] });
    assert.equal(oversized.status, 413);

    const fake = Buffer.from('GIF89a not a png').toString('base64');
    const wrongMagic = await send({ text: 'x', attachments: [{ name: 'a.png', mediaType: 'image/png', data: fake }] });
    assert.equal(wrongMagic.status, 415);

    const pdf = await send({ text: 'x', attachments: [{ name: 'a.pdf', mediaType: 'application/pdf', data: fake }] });
    assert.equal(pdf.status, 415);

    const tooMany = await send({
      text: 'x',
      attachments: Array.from({ length: 7 }, (_, i) => ({ name: `${i}.txt`, mediaType: 'text/plain', data: 'aGk=' })),
    });
    assert.equal(tooMany.status, 413);

    assert.equal((await send({ text: '  ' })).status, 400);
    assert.deepEqual(app.store.listConversations('dev@localhost'), []);
  } finally {
    await app.close();
  }
});

test('attachments are stored, served to their owner and sent to the model as image blocks', async () => {
  const transport = fakeTransport([turnFrames({ text: ['A PNG.'] })]);
  const app = await startApp({ fetch: transport.fetch });
  try {
    const response = await postJson(`${app.url}/api/assistant/conversations/new/messages`, {
      text: '',
      attachments: [
        { name: 'photo.png', mediaType: 'image/png', data: PNG.toString('base64') },
        { name: 'notes.md', mediaType: 'text/markdown', data: Buffer.from('# Notes').toString('base64') },
      ],
    });
    const events = parseEvents(await response.text());
    const attachment = events[1].data.message.attachments[0];
    assert.deepEqual(Object.keys(attachment).sort(), ['id', 'mediaType', 'name', 'size']);
    const served = await fetch(`${app.url}/api/assistant/attachments/${attachment.id}`);
    assert.equal(served.headers.get('content-type'), 'image/png');
    assert.equal(served.headers.get('cache-control'), 'private, max-age=3600');
    assert.deepEqual(Buffer.from(await served.arrayBuffer()), PNG);

    const content = transport.requests[0].body.messages[0].content;
    assert.equal(content[0].type, 'image');
    assert.match(content[1].text, /Attached file "notes.md"/);
  } finally {
    await app.close();
  }
});

test('one active stream per user (409) and at most 20 messages in 10 minutes (429)', async () => {
  const turns = [{ hang: turnFrames({ text: ['…'] }).slice(0, 3) }];
  for (let index = 0; index < 20; index += 1) turns.push(turnFrames({ text: ['ok'] }));
  const app = await startApp({ fetch: fakeTransport(turns).fetch });
  const url = `${app.url}/api/assistant/conversations/new/messages`;
  try {
    const first = await postJson(url, { text: 'one' });
    const reader = first.body.getReader();
    await reader.read();
    const busy = await postJson(url, { text: 'two' });
    assert.equal(busy.status, 409);
    await reader.cancel();
    for (let attempt = 0; attempt < 50; attempt += 1) {
      await delay(20);
      const [conversation] = app.store.listConversations('dev@localhost');
      if (app.store.listMessages('dev@localhost', conversation.id).length === 2) break;
    }
    for (let index = 1; index < 20; index += 1) await (await postJson(url, { text: `m${index}` })).text();
    const limited = await postJson(url, { text: 'too many' });
    assert.equal(limited.status, 429);
    assert.equal((await limited.json()).error.code, 'rate_limited');
  } finally {
    await app.close();
  }
});

test('history loads bytes only for images of the last two image turns and text files in the window', () => {
  const image = (id) => ({ id, name: `${id}.png`, mediaType: 'image/png', size: 8 });
  const user = (id, attachments = []) => ({ id, role: 'user', text: id, status: 'complete', attachments });
  const reply = (id) => ({ id, role: 'assistant', text: `re ${id}`, status: 'complete', attachments: [] });
  const notes = { id: 'n1', name: 'notes.md', mediaType: 'text/markdown', size: 7 };
  const loaded = [];
  const loadData = (ids) => {
    loaded.push(...ids);
    return new Map(ids.map((id) => [id, id === 'n1' ? Buffer.from('# Notes') : PNG]));
  };
  const history = buildHistory(
    [user('u1', [image('i1'), notes]), reply('a1'), user('u2', [image('i2')]), reply('a2'), user('u3', [image('i3')])],
    loadData,
  );
  assert.deepEqual(loaded.sort(), ['i2', 'i3', 'n1']);
  const kinds = history.filter((m) => m.role === 'user').map((m) => m.content[0].type);
  assert.deepEqual(kinds, ['text', 'image', 'image']);
  assert.match(history[0].content[1].text, /Attached file "notes.md"/);
});

test('history beyond ~60k characters is cut from the oldest end without loading its bytes', () => {
  const big = { id: 'old', name: 'big.txt', mediaType: 'text/plain', size: 70_000 };
  const loaded = [];
  const history = buildHistory(
    [
      { id: 'u1', role: 'user', text: 'old', status: 'complete', attachments: [big] },
      { id: 'a1', role: 'assistant', text: 'ok', status: 'complete', attachments: [] },
      { id: 'u2', role: 'user', text: 'new', status: 'complete', attachments: [] },
    ],
    (ids) => {
      loaded.push(...ids);
      return new Map();
    },
  );
  assert.deepEqual(loaded, []);
  assert.deepEqual(history, [{ role: 'user', content: [{ type: 'text', text: 'new' }] }]);
});

test('after six tool rounds the last request keeps the tools, forbids calls and the answer completes', async () => {
  const turns = [];
  for (let round = 0; round < 6; round += 1) {
    turns.push(turnFrames({ tools: [{ id: `tool_${round}`, name: 'search_docs', input: { query: `fuse ${round}` } }] }));
  }
  turns.push(turnFrames({ text: ['Final answer.'] }));
  const transport = fakeTransport(turns);
  const app = await startApp({ fetch: transport.fetch });
  try {
    const response = await postJson(`${app.url}/api/assistant/conversations/new/messages`, { text: 'Fuses?' });
    const events = parseEvents(await response.text());
    assert.equal(events.filter((e) => e.event === 'status').length, 6);
    assert.equal(events.at(-1).event, 'done');
    assert.equal(events.at(-1).data.message.text, 'Final answer.');
    assert.equal(transport.requests.length, 7);
    for (const request of transport.requests.slice(0, 6)) {
      assert.equal(request.body.tools.length, 4);
      assert.equal(request.body.tool_choice, undefined);
    }
    const last = transport.requests[6].body;
    assert.equal(last.tools.length, 4);
    assert.deepEqual(last.tool_choice, { type: 'none' });
  } finally {
    await app.close();
  }
});

test('regenerate answers the last user message again without storing it twice', async () => {
  const transport = fakeTransport([turnFrames({ text: ['First.'] }), turnFrames({ text: ['Second.'] })]);
  const app = await startApp({ fetch: transport.fetch });
  try {
    const first = parseEvents(await (await postJson(`${app.url}/api/assistant/conversations/new/messages`, { text: 'Q' })).text());
    const id = first[0].data.conversation.id;
    const response = await postJson(`${app.url}/api/assistant/conversations/${id}/regenerate`, { locale: 'en' });
    assert.equal(response.status, 200);
    const events = parseEvents(await response.text());
    assert.deepEqual(events.map((e) => e.event), ['conversation', 'delta', 'done']);
    const messages = app.store.listMessages('dev@localhost', id);
    assert.deepEqual(messages.map((m) => [m.role, m.text]), [['user', 'Q'], ['assistant', 'Second.']]);
    assert.deepEqual(transport.requests[1].body.messages, [{ role: 'user', content: [{ type: 'text', text: 'Q' }] }]);

    const empty = app.store.createConversation('dev@localhost');
    assert.equal((await postJson(`${app.url}/api/assistant/conversations/${empty.id}/regenerate`, {})).status, 404);
    assert.equal((await postJson(`${app.url}/api/assistant/conversations/nope/regenerate`, {})).status, 404);
  } finally {
    await app.close();
  }
});

test('the attachment quota refuses what would exceed it with 413 quota_exceeded', async () => {
  const app = await startApp({ env: { ASSISTANT_QUOTA_BYTES: '20' }, fetch: fakeTransport([turnFrames({ text: ['ok'] })]).fetch });
  const send = (data) => postJson(`${app.url}/api/assistant/conversations/new/messages`, {
    text: 'x',
    attachments: [{ name: 'a.txt', mediaType: 'text/plain', data: Buffer.from(data).toString('base64') }],
  });
  try {
    assert.equal((await send('0123456789abcdef')).status, 200);
    const refused = await send('01234');
    assert.equal(refused.status, 413);
    assert.equal((await refused.json()).error.code, 'quota_exceeded');
  } finally {
    await app.close();
  }
});

test('JSON routes other than messages accept at most 64 KiB', async () => {
  const app = await startApp();
  try {
    const response = await postJson(`${app.url}/api/assistant/conversations`, { title: 'x'.repeat(70 * 1024) });
    assert.equal(response.status, 413);
  } finally {
    await app.close();
  }
});
