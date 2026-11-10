// The assistant's HTTP service: chat API (SSO lane), MCP endpoint and agent files (SSO and machine
// lanes), health. Run with `node src/server.mjs`; tests build it with `createApp`.

import { createReadStream, readFileSync, statSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';

import { parseAttachments } from './attachments.mjs';
import { createAuth } from './auth.mjs';
import { answer } from './chat.mjs';
import { BOUNDS, ConfigError, LIMITS, loadConfig } from './config.mjs';
import { expectObject, HttpError, readJson, SECURITY_HEADERS, sendError, sendJson } from './http.mjs';
import { Knowledge } from './knowledge.mjs';
import { handleMcp, parseError } from './mcp.mjs';
import { createModelClient, modelKeyFor } from './model.mjs';
import { Store } from './store.mjs';

const VERSION = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).version;

const SHUTDOWN_GRACE_MS = 10_000;
const MAX_PAGE_PATH_CHARS = 500;
const MAX_PAGE_TITLE_CHARS = 300;

/** Agent files under `/api/agent/`, mapped to their place below KNOWLEDGE_DIR/public. */
const AGENT_FILES = new Map([
  ['llms.txt', { file: 'llms.txt', type: 'text/plain; charset=utf-8' }],
  ['llms-full.txt', { file: 'llms-full.txt', type: 'text/plain; charset=utf-8' }],
  ['de/llms.txt', { file: 'de/llms.txt', type: 'text/plain; charset=utf-8' }],
  ['de/llms-full.txt', { file: 'de/llms-full.txt', type: 'text/plain; charset=utf-8' }],
  ['strido-skill.zip', { file: 'downloads/strido-skill.zip', type: 'application/zip' }],
]);

/** Matches `/api/assistant/conversations/<id>` with an optional `/messages` or `/regenerate`; captures id and action. */
const CONVERSATION_ROUTE = /^\/api\/assistant\/conversations\/([\w-]{1,64})(?:\/(messages|regenerate))?$/;

/** Matches `/api/assistant/attachments/<id>` and captures the id. */
const ATTACHMENT_ROUTE = /^\/api\/assistant\/attachments\/([\w-]{1,64})$/;

/** Matches `/api/agent/<file>` and captures the file name (with an optional `de/`). */
const AGENT_ROUTE = /^\/api\/agent\/((?:de\/)?[\w.-]+)$/;

function badRequest(message) {
  return new HttpError(400, 'invalid_request', message);
}

function parseTitle(value) {
  if (typeof value !== 'string') throw badRequest('title must be a string.');
  const title = value.trim();
  if (title.length < 1 || title.length > BOUNDS.maxTitleChars) throw badRequest(`title must be 1..${BOUNDS.maxTitleChars} characters.`);
  return title;
}

function parsePageContext(value) {
  if (value === undefined || value === null) return null;
  expectObject(value, 'page');
  const pagePath = typeof value.path === 'string' ? value.path.slice(0, MAX_PAGE_PATH_CHARS) : '';
  const title = typeof value.title === 'string' ? value.title.slice(0, MAX_PAGE_TITLE_CHARS) : '';
  return pagePath === '' ? null : { path: pagePath, title };
}

/**
 * Build the service.
 * @param deps `{config, knowledge, store, model, auth}`; `model` is `createModelClient(...)` (tests
 *   inject one with a fake fetch), `auth` is `createAuth(...)`.
 */
export function createApp({ config, knowledge, store, model, auth }) {
  /** email -> {conversationId, controller} of the answer streaming for that user. */
  const active = new Map();
  /** email -> timestamps of accepted messages inside the rate window. */
  const recent = new Map();

  function withinRate(email, now) {
    const kept = (recent.get(email) ?? []).filter((at) => now - at < BOUNDS.messageWindowMs);
    recent.set(email, kept);
    return kept.length < BOUNDS.messagesPerWindow;
  }

  function ownConversation(user, id) {
    const conversation = store.getConversation(user.email, id);
    if (conversation === null) throw new HttpError(404, 'not_found', 'No such conversation.');
    return conversation;
  }

  function checkRoom(user) {
    if (store.countConversations(user.email) >= BOUNDS.maxConversations) {
      throw new HttpError(409, 'too_many_conversations', `You have ${BOUNDS.maxConversations} conversations; delete some to start a new one.`);
    }
  }

  /** The key for this user's answer, or the refusal as an HttpError. */
  function modelKey(user) {
    const choice = modelKeyFor(config.model, user.email);
    if (choice.error) throw new HttpError(choice.error.status, choice.error.code, choice.error.message);
    return choice.key;
  }

  /** 409 while this user's answer streams, 429 above the message rate; returns the time to record. */
  function admit(user) {
    if (active.has(user.email)) throw new HttpError(409, 'busy', 'Another answer is still running. Stop it or wait for it.');
    const now = Date.now();
    if (!withinRate(user.email, now)) {
      throw new HttpError(429, 'rate_limited', `At most ${BOUNDS.messagesPerWindow} messages in 10 minutes. Try again shortly.`);
    }
    return now;
  }

  /**
   * Stream an answer to the conversation's last user message as SSE: `conversation`, `user` (when
   * `prepare` returns the stored user message), then what `answer` emits.
   * @param options.prepare runs once the stream is admitted: stores the user's message and returns
   *   it, or drops the old answers (regenerate) and returns null
   */
  async function streamAnswer(res, user, { conversationId, key, locale, page, admittedAt, prepare }) {
    const controller = new AbortController();
    active.set(user.email, { conversationId, controller });
    recent.get(user.email).push(admittedAt);
    let ping;
    try {
      const userMessage = prepare();
      res.writeHead(200, {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-store',
        'x-accel-buffering': 'no',
        connection: 'keep-alive',
      });
      res.on('close', () => {
        if (!res.writableEnded) controller.abort();
      });
      const emit = (name, data) => {
        if (!res.writableEnded && !res.destroyed) res.write(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`);
      };
      ping = setInterval(() => {
        if (!res.writableEnded && !res.destroyed) res.write(': ping\n\n');
      }, BOUNDS.pingIntervalMs);
      emit('conversation', { conversation: store.getConversation(user.email, conversationId) });
      if (userMessage !== null) emit('user', { message: userMessage });
      await answer({
        store,
        knowledge,
        model,
        key,
        owner: user.email,
        conversationId,
        locale,
        page,
        signal: controller.signal,
        emit,
        siteUrl: config.siteUrl,
      });
    } finally {
      clearInterval(ping);
      active.delete(user.email);
      if (res.headersSent && !res.writableEnded) res.end();
    }
  }

  async function postMessage(req, res, user, conversationId) {
    const key = modelKey(user);
    const body = expectObject(await readJson(req, BOUNDS.messageBodyBytes));
    const text = body.text ?? '';
    if (typeof text !== 'string') throw badRequest('text must be a string.');
    if (text.length > LIMITS.maxPromptChars) throw new HttpError(413, 'too_large', `The message is longer than ${LIMITS.maxPromptChars} characters.`);
    const attachments = parseAttachments(body.attachments);
    if (text.trim() === '' && attachments.length === 0) throw badRequest('Write a message or attach a file.');
    const added = attachments.reduce((sum, attachment) => sum + attachment.data.length, 0);
    if (added > 0 && store.attachmentBytes(user.email) + added > config.quotaBytes) {
      throw new HttpError(413, 'quota_exceeded', 'Your stored attachments use all your space. Delete old conversations to attach more.');
    }
    const admittedAt = admit(user);
    let conversation;
    if (conversationId === 'new') {
      checkRoom(user);
      conversation = store.createConversation(user.email);
    } else {
      conversation = ownConversation(user, conversationId);
    }
    await streamAnswer(res, user, {
      conversationId: conversation.id,
      key,
      locale: body.locale === 'de' ? 'de' : 'en',
      page: parsePageContext(body.page),
      admittedAt,
      prepare: () => store.addMessage(user.email, conversation.id, { role: 'user', text, attachments }),
    });
  }

  /** Answer the conversation's last user message again, replacing the answers after it. */
  async function regenerate(req, res, user, conversationId) {
    const key = modelKey(user);
    const body = expectObject(await readJson(req, BOUNDS.jsonBodyBytes));
    const page = parsePageContext(body.page);
    const admittedAt = admit(user);
    ownConversation(user, conversationId);
    if (!store.listMessages(user.email, conversationId).some((message) => message.role === 'user')) {
      throw new HttpError(404, 'not_found', 'This conversation has no question to answer again.');
    }
    await streamAnswer(res, user, {
      conversationId,
      key,
      locale: body.locale === 'de' ? 'de' : 'en',
      page,
      admittedAt,
      prepare: () => {
        store.dropAnswersAfterLastUser(user.email, conversationId);
        return null;
      },
    });
  }

  function me(user) {
    const choice = modelKeyFor(config.model, user.email);
    return {
      user: { email: user.email, name: user.name },
      enabled: choice.error === undefined,
      ...(choice.error ? { reason: choice.error.message } : {}),
      model: config.model.id,
      limits: LIMITS,
    };
  }

  function serveAgentFile(res, name) {
    const entry = AGENT_FILES.get(name);
    if (entry === undefined) throw new HttpError(404, 'not_found', 'No such agent file.');
    const file = path.join(config.knowledgeDir, 'public', entry.file);
    let size;
    try {
      size = statSync(file).size;
    } catch {
      throw new HttpError(404, 'not_found', 'This agent file has not been generated.');
    }
    res.writeHead(200, { 'content-type': entry.type, 'content-length': size, 'cache-control': 'private, max-age=300' });
    createReadStream(file).on('error', () => res.destroy()).pipe(res);
  }

  async function serveMcp(req, res) {
    let message;
    try {
      message = await readJson(req, BOUNDS.jsonBodyBytes);
    } catch (error) {
      if (error instanceof HttpError && error.code === 'invalid_json') return sendJson(res, 400, parseError());
      throw error;
    }
    const reply = handleMcp(message, { knowledge, siteUrl: config.siteUrl, version: VERSION });
    if (reply === null) {
      res.writeHead(202, { 'content-length': 0 });
      return res.end();
    }
    return sendJson(res, 200, reply);
  }

  async function route(req, res) {
    const url = new URL(req.url ?? '/', 'http://localhost');
    const { pathname } = url;
    const method = req.method ?? 'GET';

    if (pathname === '/api/health' && method === 'GET') {
      const configured = config.model.baseUrl !== '' && (config.model.sharedKey !== '' || config.model.subscriberKey !== '');
      return sendJson(res, 200, { ok: true, pages: knowledge.counts(), model: { configured } });
    }
    if (pathname === '/mcp') {
      if (method !== 'POST') return sendJson(res, 405, { error: { code: 'method_not_allowed', message: 'POST JSON-RPC messages.' } }, { allow: 'POST' });
      await auth.identify(req, true);
      return serveMcp(req, res);
    }
    const agentFile = AGENT_ROUTE.exec(pathname);
    if (agentFile !== null && method === 'GET') {
      await auth.identify(req, true);
      return serveAgentFile(res, agentFile[1]);
    }
    if (!pathname.startsWith('/api/assistant/')) throw new HttpError(404, 'not_found', 'Not found.');

    const user = await auth.identify(req, false);
    if (pathname === '/api/assistant/me' && method === 'GET') return sendJson(res, 200, me(user));
    if (pathname === '/api/assistant/conversations') {
      if (method === 'GET') return sendJson(res, 200, { conversations: store.listConversations(user.email) });
      if (method === 'POST') {
        const body = expectObject(await readJson(req, BOUNDS.jsonBodyBytes));
        const title = body.title === undefined || body.title === '' ? '' : parseTitle(body.title);
        checkRoom(user);
        return sendJson(res, 201, { conversation: store.createConversation(user.email, title) });
      }
    }
    const conversationRoute = CONVERSATION_ROUTE.exec(pathname);
    if (conversationRoute !== null) {
      const [, id, action] = conversationRoute;
      if (action === 'regenerate') {
        if (method === 'POST') return regenerate(req, res, user, id);
      } else if (action === 'messages') {
        if (method === 'POST') return postMessage(req, res, user, id);
        if (method === 'GET') {
          const list = store.listMessages(user.email, id);
          if (list === null) throw new HttpError(404, 'not_found', 'No such conversation.');
          return sendJson(res, 200, { messages: list });
        }
      } else if (method === 'PATCH') {
        const title = parseTitle(expectObject(await readJson(req, BOUNDS.jsonBodyBytes)).title);
        const conversation = store.renameConversation(user.email, id, title);
        if (conversation === null) throw new HttpError(404, 'not_found', 'No such conversation.');
        return sendJson(res, 200, { conversation });
      } else if (method === 'DELETE') {
        ownConversation(user, id);
        if (active.get(user.email)?.conversationId === id) {
          throw new HttpError(409, 'busy', 'An answer is still running in this conversation.');
        }
        store.deleteConversation(user.email, id);
        res.writeHead(204);
        return res.end();
      }
    }
    const attachmentRoute = ATTACHMENT_ROUTE.exec(pathname);
    if (attachmentRoute !== null && method === 'GET') {
      const attachment = store.getAttachment(user.email, attachmentRoute[1]);
      if (attachment === null) throw new HttpError(404, 'not_found', 'No such attachment.');
      res.writeHead(200, {
        'content-type': attachment.mediaType,
        'content-length': attachment.data.length,
        'cache-control': 'private, max-age=3600',
        'content-disposition': `inline; filename*=UTF-8''${encodeURIComponent(attachment.name)}`,
      });
      return res.end(attachment.data);
    }
    throw new HttpError(404, 'not_found', 'Not found.');
  }

  const server = http.createServer((req, res) => {
    for (const [name, value] of Object.entries(SECURITY_HEADERS)) res.setHeader(name, value);
    route(req, res).catch((error) => {
      if (!(error instanceof HttpError)) {
        console.error(`assistant: ${req.method} ${req.url?.split('?')[0]} failed: ${error?.message ?? error}`);
        error = new HttpError(500, 'internal', 'Something went wrong.');
      }
      sendError(res, error);
    });
  });

  /** Stop accepting, stop running answers (stored as `stopped`), wait for them, close. */
  async function close() {
    const closed = new Promise((resolve) => server.close(resolve));
    for (const { controller } of active.values()) controller.abort();
    server.closeIdleConnections();
    const grace = setTimeout(() => server.closeAllConnections(), SHUTDOWN_GRACE_MS);
    await closed;
    clearTimeout(grace);
  }

  return { server, close };
}

async function main() {
  let config;
  try {
    config = loadConfig();
  } catch (error) {
    if (!(error instanceof ConfigError)) throw error;
    console.error(`assistant: ${error.message}`);
    process.exit(2);
  }
  const knowledge = new Knowledge(config.knowledgeDir);
  const store = new Store(path.join(config.dataDir, 'assistant.db'));
  const model = createModelClient({ baseUrl: config.model.baseUrl, model: config.model.id });
  const app = createApp({ config, knowledge, store, model, auth: createAuth(config.auth) });
  app.server.listen(config.port, config.host, () => {
    const pages = knowledge.counts();
    console.log(`assistant ${VERSION} on ${config.host}:${config.port} (${config.auth.mode} auth, ${pages.en} en / ${pages.de} de pages, model ${config.model.id})`);
  });
  let stopping = false;
  const stop = async () => {
    if (stopping) return;
    stopping = true;
    await app.close();
    store.close();
    process.exit(0);
  };
  process.on('SIGTERM', stop);
  process.on('SIGINT', stop);
}

if (import.meta.main) await main();
