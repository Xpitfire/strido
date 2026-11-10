// Conversations, messages and attachments in SQLite (node:sqlite, WAL). Every read and write is scoped
// by the owner's email: a row of another owner is indistinguishable from a missing one.

import { randomUUID } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

import { BOUNDS } from './config.mjs';

export const DEFAULT_TITLE = 'New conversation';

/** Schema steps; `PRAGMA user_version` counts the ones applied. Append only. */
const MIGRATIONS = [
  `CREATE TABLE conversations (
     id TEXT PRIMARY KEY,
     owner TEXT NOT NULL,
     title TEXT NOT NULL,
     titled INTEGER NOT NULL DEFAULT 0,
     created_at INTEGER NOT NULL,
     updated_at INTEGER NOT NULL
   );
   CREATE INDEX conversations_owner ON conversations(owner, updated_at DESC);
   CREATE TABLE messages (
     seq INTEGER PRIMARY KEY AUTOINCREMENT,
     id TEXT NOT NULL UNIQUE,
     conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
     role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
     text TEXT NOT NULL,
     status TEXT NOT NULL CHECK (status IN ('complete', 'stopped', 'error')),
     sources TEXT NOT NULL DEFAULT '[]',
     created_at INTEGER NOT NULL
   );
   CREATE INDEX messages_conversation ON messages(conversation_id, seq);
   CREATE TABLE attachments (
     seq INTEGER PRIMARY KEY AUTOINCREMENT,
     id TEXT NOT NULL UNIQUE,
     message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
     owner TEXT NOT NULL,
     name TEXT NOT NULL,
     media_type TEXT NOT NULL,
     size INTEGER NOT NULL,
     data BLOB NOT NULL
   );
   CREATE INDEX attachments_message ON attachments(message_id, seq);`,
];

/** Matches runs of whitespace (titles are one line). */
const WHITESPACE = /\s+/g;

/** A title from the first user message: one line, at most 60 characters. */
export function autoTitle(text, attachmentNames = []) {
  const line = text.replace(WHITESPACE, ' ').trim() || attachmentNames[0] || DEFAULT_TITLE;
  const max = BOUNDS.autoTitleChars;
  return line.length <= max ? line : `${line.slice(0, max - 1).trimEnd()}…`;
}

function conversationOut(row) {
  return {
    id: row.id,
    title: row.title,
    createdAt: new Date(row.created_at).toISOString(),
    updatedAt: new Date(row.updated_at).toISOString(),
    messageCount: row.message_count ?? 0,
  };
}

export class Store {
  #db;
  #now;

  /** @param file a path, or ':memory:' */
  constructor(file, { now = Date.now } = {}) {
    if (file !== ':memory:') mkdirSync(path.dirname(file), { recursive: true });
    this.#db = new DatabaseSync(file);
    this.#now = now;
    // Must precede WAL and the first table: deleted conversations' pages then go back to the file system.
    if (this.#db.prepare('PRAGMA user_version').get().user_version === 0) this.#db.exec('PRAGMA auto_vacuum = INCREMENTAL');
    this.#db.exec('PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON; PRAGMA busy_timeout = 5000;');
    this.#migrate();
  }

  #migrate() {
    const { user_version: version } = this.#db.prepare('PRAGMA user_version').get();
    for (let step = version; step < MIGRATIONS.length; step += 1) {
      this.#db.exec('BEGIN');
      try {
        this.#db.exec(MIGRATIONS[step]);
        this.#db.exec(`PRAGMA user_version = ${step + 1}`);
        this.#db.exec('COMMIT');
      } catch (error) {
        this.#db.exec('ROLLBACK');
        throw error;
      }
    }
  }

  close() {
    this.#db.close();
  }

  listConversations(owner) {
    return this.#db
      .prepare(
        `SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
           FROM conversations c WHERE c.owner = ? ORDER BY c.updated_at DESC, c.rowid DESC`,
      )
      .all(owner)
      .map(conversationOut);
  }

  countConversations(owner) {
    return this.#db.prepare('SELECT COUNT(*) AS n FROM conversations WHERE owner = ?').get(owner).n;
  }

  /** The conversation, or null when it does not exist or belongs to someone else. */
  getConversation(owner, id) {
    const row = this.#db
      .prepare(
        `SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
           FROM conversations c WHERE c.id = ? AND c.owner = ?`,
      )
      .get(id, owner);
    return row === undefined ? null : conversationOut(row);
  }

  createConversation(owner, title = '') {
    const id = randomUUID();
    const now = this.#now();
    const titled = title !== '';
    this.#db
      .prepare('INSERT INTO conversations (id, owner, title, titled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)')
      .run(id, owner, titled ? title : DEFAULT_TITLE, titled ? 1 : 0, now, now);
    return this.getConversation(owner, id);
  }

  /** The renamed conversation, or null when it is not the owner's. */
  renameConversation(owner, id, title) {
    const result = this.#db
      .prepare('UPDATE conversations SET title = ?, titled = 1, updated_at = ? WHERE id = ? AND owner = ?')
      .run(title, this.#now(), id, owner);
    return result.changes === 0 ? null : this.getConversation(owner, id);
  }

  /** Whether a conversation of the owner was deleted (with its messages and attachments). */
  deleteConversation(owner, id) {
    const deleted = this.#db.prepare('DELETE FROM conversations WHERE id = ? AND owner = ?').run(id, owner).changes > 0;
    if (deleted) this.#db.exec('PRAGMA incremental_vacuum');
    return deleted;
  }

  /** Bytes of all the owner's stored attachments (the disk quota counts these). */
  attachmentBytes(owner) {
    return this.#db.prepare('SELECT COALESCE(SUM(size), 0) AS n FROM attachments WHERE owner = ?').get(owner).n;
  }

  /** Messages oldest first (attachments without their bytes), or null when the conversation is not the owner's. */
  listMessages(owner, conversationId) {
    if (this.getConversation(owner, conversationId) === null) return null;
    const rows = this.#db
      .prepare('SELECT * FROM messages WHERE conversation_id = ? ORDER BY seq')
      .all(conversationId);
    const attachments = this.#db
      .prepare(
        `SELECT a.id, a.message_id, a.name, a.media_type, a.size
           FROM attachments a JOIN messages m ON m.id = a.message_id
          WHERE m.conversation_id = ? AND a.owner = ? ORDER BY a.seq`,
      )
      .all(conversationId, owner);
    const byMessage = Map.groupBy(attachments, (row) => row.message_id);
    return rows.map((row) => this.#messageOut(row, byMessage.get(row.id) ?? []));
  }

  /** The bytes of the owner's attachments with these ids, as `Map<id, Buffer>`. */
  attachmentData(owner, ids) {
    const select = this.#db.prepare('SELECT data FROM attachments WHERE id = ? AND owner = ?');
    const data = new Map();
    for (const id of ids) {
      const row = select.get(id, owner);
      if (row !== undefined) data.set(id, Buffer.from(row.data));
    }
    return data;
  }

  /**
   * Delete the answers after the conversation's last user message (to answer it again). Returns that
   * user message's id, or null when the conversation is not the owner's or has no user message.
   */
  dropAnswersAfterLastUser(owner, conversationId) {
    if (this.getConversation(owner, conversationId) === null) return null;
    const last = this.#db
      .prepare("SELECT id, seq FROM messages WHERE conversation_id = ? AND role = 'user' ORDER BY seq DESC LIMIT 1")
      .get(conversationId);
    if (last === undefined) return null;
    this.#db.prepare('DELETE FROM messages WHERE conversation_id = ? AND seq > ?').run(conversationId, last.seq);
    return last.id;
  }

  #messageOut(row, attachments) {
    return {
      id: row.id,
      role: row.role,
      text: row.text,
      status: row.status,
      attachments: attachments.map((a) => ({ id: a.id, name: a.name, mediaType: a.media_type, size: a.size })),
      sources: JSON.parse(row.sources),
      createdAt: new Date(row.created_at).toISOString(),
    };
  }

  /**
   * Store a message (and its attachments) in one transaction; a first user message titles a
   * conversation that has no title yet. Returns the message without attachment bytes, or null when
   * the conversation is not the owner's.
   */
  addMessage(owner, conversationId, { role, text, status = 'complete', sources = [], attachments = [] }) {
    if (this.getConversation(owner, conversationId) === null) return null;
    const id = randomUUID();
    const now = this.#now();
    this.#db.exec('BEGIN');
    try {
      this.#db
        .prepare('INSERT INTO messages (id, conversation_id, role, text, status, sources, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)')
        .run(id, conversationId, role, text, status, JSON.stringify(sources), now);
      const insert = this.#db.prepare(
        'INSERT INTO attachments (id, message_id, owner, name, media_type, size, data) VALUES (?, ?, ?, ?, ?, ?, ?)',
      );
      for (const attachment of attachments) {
        insert.run(randomUUID(), id, owner, attachment.name, attachment.mediaType, attachment.data.length, attachment.data);
      }
      if (role === 'user') {
        this.#db
          .prepare('UPDATE conversations SET title = ?, titled = 1 WHERE id = ? AND titled = 0')
          .run(autoTitle(text, attachments.map((a) => a.name)), conversationId);
      }
      this.#db.prepare('UPDATE conversations SET updated_at = ? WHERE id = ?').run(now, conversationId);
      this.#db.exec('COMMIT');
    } catch (error) {
      this.#db.exec('ROLLBACK');
      throw error;
    }
    const row = this.#db.prepare('SELECT * FROM messages WHERE id = ?').get(id);
    const stored = this.#db
      .prepare('SELECT id, message_id, name, media_type, size FROM attachments WHERE message_id = ? ORDER BY seq')
      .all(id);
    return this.#messageOut(row, stored);
  }

  /** `{name, mediaType, data}` of the owner's attachment, or null. */
  getAttachment(owner, id) {
    const row = this.#db.prepare('SELECT name, media_type, data FROM attachments WHERE id = ? AND owner = ?').get(id, owner);
    return row === undefined ? null : { name: row.name, mediaType: row.media_type, data: Buffer.from(row.data) };
  }
}
