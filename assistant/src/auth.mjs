// Who is asking. Three ways in (contract "Auth"):
// - dev: a fixed user, no checks (config refuses it without ASSISTANT_DEV=1);
// - SSO lane: the Cortex gateway's `X-Cortex-Email`/`X-Cortex-User`, trusted only when the request also
//   carries `X-Cortex-Auth-Secret` equal to CORTEX_APP_HEADER_SECRET (compared in constant time);
// - machine lane: `Authorization: Bearer cxu_…`, a Cortex per-user app token, verified with the app key
//   (the file at CORTEX_APP_KEY_FILE) on Control's app-directory lane at CORTEX_APP_DIRECTORY_URL.
//   Answers (current or refused) are cached for at most a minute; the lane reaches `/mcp` and
//   `/api/agent/*` only.

import { createHash, timingSafeEqual } from 'node:crypto';
import { readFileSync } from 'node:fs';

import { BOUNDS } from './config.mjs';
import { HttpError } from './http.mjs';

export const DEV_USER = Object.freeze({ email: 'dev@localhost', name: 'Developer' });

const APP_TOKEN_PREFIX = 'cxu_';

/** Matches `Bearer <token>` and captures the token. */
const BEARER = /^Bearer\s+(\S+)$/i;

/** Upper bound of cached token answers, so a flood of distinct tokens cannot grow memory. */
const MAX_CACHED_TOKENS = 1000;

function sameSecret(given, expected) {
  const left = Buffer.from(given, 'utf8');
  const right = Buffer.from(expected, 'utf8');
  // timingSafeEqual throws on a length mismatch; checking the length first leaks only the length.
  return left.length === right.length && timingSafeEqual(left, right);
}

function header(req, name) {
  const value = req.headers[name];
  return (Array.isArray(value) ? value[0] : value ?? '').trim();
}

/** The app-directory verify URL. CORTEX_APP_DIRECTORY_URL normally already ends in `/api/v1/app-directory`. */
export function verifyUrl(directoryUrl) {
  // Already the app-directory base (Control injects it that way), or just the Control origin.
  const base = /\/api\/v1\/app-directory$/.test(directoryUrl) ? directoryUrl : `${directoryUrl}/api/v1/app-directory`;
  return `${base}/tokens/verify`;
}

/**
 * @param config the `auth` part of the configuration
 * @param options.fetch substitute for `fetch` (tests)
 * @param options.readKey substitute for reading the app key file (tests)
 */
export function createAuth(config, options = {}) {
  const fetcher = options.fetch ?? globalThis.fetch;
  const readKey = options.readKey ?? (() => readFileSync(config.appKeyFile, 'utf8'));
  const now = options.now ?? Date.now;
  /** sha256(token) -> {user, until} for current tokens; never the token itself. */
  const tokenCache = new Map();
  /** sha256(token) -> until for refused tokens, so made-up tokens cannot drain Control's verify budget. */
  const refusedCache = new Map();
  let appKey = null;

  /** Set a cache entry, evicting the oldest one at the bound. */
  function remember(cache, digest, value) {
    cache.delete(digest);
    if (cache.size >= MAX_CACHED_TOKENS) cache.delete(cache.keys().next().value);
    cache.set(digest, value);
  }

  function key() {
    if (appKey === null) {
      try {
        appKey = readKey().trim();
      } catch {
        throw new HttpError(503, 'cortex_unreachable', 'Cortex could not confirm that app token just now.');
      }
    }
    return appKey;
  }

  async function ask(token, usedKey) {
    try {
      return await fetcher(verifyUrl(config.directoryUrl), {
        method: 'POST',
        headers: { authorization: `Bearer ${usedKey}`, 'content-type': 'application/json' },
        body: JSON.stringify({ token }),
        redirect: 'error',
        signal: AbortSignal.timeout(BOUNDS.tokenVerifyTimeoutMs),
      });
    } catch {
      throw new HttpError(503, 'cortex_unreachable', 'Cortex could not confirm that app token just now.');
    }
  }

  async function verifyToken(token) {
    if (!token.startsWith(APP_TOKEN_PREFIX)) throw new HttpError(401, 'unauthorized', 'Unknown bearer token.');
    if (config.directoryUrl === '') {
      throw new HttpError(401, 'unauthorized', 'This deployment has no Cortex app key; app tokens cannot be checked.');
    }
    const digest = createHash('sha256').update(token).digest('hex');
    const cached = tokenCache.get(digest);
    if (cached !== undefined && cached.until > now()) return cached.user;
    tokenCache.delete(digest);
    const refusedUntil = refusedCache.get(digest);
    if (refusedUntil !== undefined && refusedUntil > now()) throw new HttpError(401, 'unauthorized', 'The app token is not current.');
    refusedCache.delete(digest);

    const used = key();
    let response = await ask(token, used);
    if (response.status === 401) {
      // Control rotates the key in place: re-read it, and ask again only when it changed.
      appKey = null;
      const fresh = key();
      if (fresh !== used) response = await ask(token, fresh);
    }
    if (response.status === 401) {
      remember(refusedCache, digest, now() + BOUNDS.tokenCacheMs);
      throw new HttpError(401, 'unauthorized', 'The app token is not current.');
    }
    if (response.status !== 200) throw new HttpError(503, 'cortex_unreachable', 'Cortex could not confirm that app token just now.');
    const body = await response.json().catch(() => null);
    const email = body?.user?.email;
    if (typeof email !== 'string' || email === '') {
      throw new HttpError(503, 'cortex_unreachable', 'Cortex answered the token check unexpectedly.');
    }
    const user = Object.freeze({ email: email.toLowerCase(), name: String(body.user.username ?? email) });
    const expires = Date.parse(body.expiresAt);
    const until = Math.min(now() + BOUNDS.tokenCacheMs, Number.isNaN(expires) ? Infinity : expires);
    remember(tokenCache, digest, { user, until });
    return user;
  }

  /**
   * The user of a request, or an HttpError (401 unknown, 403 lane not allowed, 503 Cortex unreachable).
   * @param machineAllowed whether the route accepts the machine lane (`/mcp`, `/api/agent/*`)
   */
  async function identify(req, machineAllowed) {
    if (config.mode === 'dev') return DEV_USER;
    const bearer = BEARER.exec(header(req, 'authorization'));
    if (bearer !== null) {
      if (!machineAllowed) throw new HttpError(403, 'forbidden', 'App tokens reach /mcp and /api/agent/ only.');
      return verifyToken(bearer[1]);
    }
    const secret = header(req, 'x-cortex-auth-secret');
    if (secret === '' || !sameSecret(secret, config.headerSecret)) {
      throw new HttpError(401, 'unauthorized', 'Sign in through Cortex.');
    }
    const login = header(req, 'x-cortex-user');
    const email = (header(req, 'x-cortex-email') || login).toLowerCase();
    if (email === '') throw new HttpError(401, 'unauthorized', 'Sign in through Cortex.');
    return Object.freeze({ email, name: login || email.split('@')[0] });
  }

  return { identify };
}
