import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { test } from 'node:test';

import { autoTitle, DEFAULT_TITLE, Store } from '../src/store.mjs';
import { postJson, startApp } from './helpers.mjs';

test('a new database uses incremental auto-vacuum; attachment bytes are counted per owner', () => {
  const directory = mkdtempSync(path.join(tmpdir(), 'assistant-store-'));
  try {
    const file = path.join(directory, 'assistant.db');
    const store = new Store(file);
    const conversation = store.createConversation('a@x');
    store.addMessage('a@x', conversation.id, {
      role: 'user',
      text: 'x',
      attachments: [{ name: 'a.txt', mediaType: 'text/plain', data: Buffer.alloc(1000, 97) }],
    });
    assert.equal(store.attachmentBytes('a@x'), 1000);
    assert.equal(store.attachmentBytes('b@x'), 0);
    assert.equal(store.deleteConversation('a@x', conversation.id), true);
    assert.equal(store.attachmentBytes('a@x'), 0);
    store.close();
    const raw = new DatabaseSync(file);
    assert.equal(raw.prepare('PRAGMA auto_vacuum').get().auto_vacuum, 2); // 2 = incremental
    raw.close();
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('store scopes conversations, messages and attachments by owner', () => {
  const store = new Store(':memory:');
  const mine = store.createConversation('anna@example.com');
  const message = store.addMessage('anna@example.com', mine.id, {
    role: 'user',
    text: 'Hello',
    attachments: [{ name: 'a.txt', mediaType: 'text/plain', data: Buffer.from('hi') }],
  });
  const attachmentId = message.attachments[0].id;

  assert.equal(store.getConversation('bob@example.com', mine.id), null);
  assert.equal(store.listMessages('bob@example.com', mine.id), null);
  assert.equal(store.renameConversation('bob@example.com', mine.id, 'Stolen'), null);
  assert.equal(store.deleteConversation('bob@example.com', mine.id), false);
  assert.equal(store.getAttachment('bob@example.com', attachmentId), null);
  assert.equal(store.addMessage('bob@example.com', mine.id, { role: 'user', text: 'x' }), null);
  assert.deepEqual(store.listConversations('bob@example.com'), []);

  assert.equal(store.getConversation('anna@example.com', mine.id).title, 'Hello');
  assert.equal(store.getAttachment('anna@example.com', attachmentId).data.toString(), 'hi');
  assert.equal(store.deleteConversation('anna@example.com', mine.id), true);
  assert.equal(store.getAttachment('anna@example.com', attachmentId), null);
  store.close();
});

test('auto title: first user message, one line, at most 60 characters; renames stick', () => {
  assert.equal(autoTitle('  Which\nfuse?  '), 'Which fuse?');
  assert.equal(autoTitle('x'.repeat(100)).length, 60);
  assert.equal(autoTitle('', ['photo.png']), 'photo.png');

  const store = new Store(':memory:');
  const conversation = store.createConversation('a@x');
  assert.equal(conversation.title, DEFAULT_TITLE);
  store.addMessage('a@x', conversation.id, { role: 'user', text: 'First question' });
  store.addMessage('a@x', conversation.id, { role: 'user', text: 'Second question' });
  assert.equal(store.getConversation('a@x', conversation.id).title, 'First question');
  assert.equal(store.getConversation('a@x', conversation.id).messageCount, 2);

  const named = store.createConversation('a@x', 'Named');
  store.addMessage('a@x', named.id, { role: 'user', text: 'Ignored for the title' });
  assert.equal(store.getConversation('a@x', named.id).title, 'Named');
  store.close();
});

test('HTTP: another user cannot read, rename or delete a conversation', async () => {
  const app = await startApp({ env: { ASSISTANT_AUTH_MODE: 'cortex', CORTEX_APP_HEADER_SECRET: 'secret' } });
  const as = (email) => ({ 'x-cortex-auth-secret': 'secret', 'x-cortex-email': email });
  try {
    const created = await postJson(`${app.url}/api/assistant/conversations`, { title: 'Mine' }, as('anna@example.com'));
    assert.equal(created.status, 201);
    const { conversation } = await created.json();
    const base = `${app.url}/api/assistant/conversations/${conversation.id}`;

    const read = await fetch(`${base}/messages`, { headers: as('bob@example.com') });
    assert.equal(read.status, 404);
    const rename = await fetch(base, {
      method: 'PATCH',
      headers: { ...as('bob@example.com'), 'content-type': 'application/json' },
      body: JSON.stringify({ title: 'Stolen' }),
    });
    assert.equal(rename.status, 404);
    const remove = await fetch(base, { method: 'DELETE', headers: as('bob@example.com') });
    assert.equal(remove.status, 404);
    const list = await (await fetch(`${app.url}/api/assistant/conversations`, { headers: as('bob@example.com') })).json();
    assert.deepEqual(list.conversations, []);

    const own = await fetch(base, {
      method: 'PATCH',
      headers: { ...as('anna@example.com'), 'content-type': 'application/json' },
      body: JSON.stringify({ title: 'Renamed' }),
    });
    assert.equal((await own.json()).conversation.title, 'Renamed');
    assert.equal((await fetch(base, { method: 'DELETE', headers: as('anna@example.com') })).status, 204);
  } finally {
    await app.close();
  }
});

test('HTTP: at most 200 conversations per user', async () => {
  const app = await startApp();
  try {
    for (let index = 0; index < 200; index += 1) app.store.createConversation('dev@localhost');
    const response = await postJson(`${app.url}/api/assistant/conversations`, {});
    assert.equal(response.status, 409);
    assert.equal((await response.json()).error.code, 'too_many_conversations');
  } finally {
    await app.close();
  }
});
