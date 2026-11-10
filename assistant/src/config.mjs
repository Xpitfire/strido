// Environment parsing. Everything the service reads from the environment is read here, once, and
// a configuration that cannot work (dev auth without the dev switch, cortex auth without the header
// secret, half of the app-directory pair) refuses to start with a message naming the variable.

import path from 'node:path';

/** Limits the API advertises in `/me` and enforces. */
export const LIMITS = Object.freeze({
  maxPromptChars: 16_000,
  maxAttachments: 6,
  // 3.75 MiB: Anthropic's 5 MB image limit applies to the base64 string (4/3 of the bytes).
  maxImageBytes: 3_932_160,
  maxTextBytes: 200 * 1024,
});

const BODY_SLACK_BYTES = 64 * 1024;

/** Server-side bounds that are not part of the public `/me` answer. */
export const BOUNDS = Object.freeze({
  /** A message: every attachment a full-size image in base64, the prompt at 4 bytes per character, slack. */
  messageBodyBytes:
    LIMITS.maxAttachments * Math.ceil(LIMITS.maxImageBytes / 3) * 4 + LIMITS.maxPromptChars * 4 + BODY_SLACK_BYTES,
  /** Every other JSON body (conversations, regenerate, MCP). */
  jsonBodyBytes: BODY_SLACK_BYTES,
  messagesPerWindow: 20,
  messageWindowMs: 10 * 60 * 1000,
  maxConversations: 200,
  maxTitleChars: 120,
  autoTitleChars: 60,
  pingIntervalMs: 15_000,
  modelTurnTimeoutMs: 120_000,
  maxToolRounds: 6,
  maxOutputTokens: 4096,
  historyMessages: 30,
  historyChars: 60_000,
  historyImageTurns: 2,
  tokenCacheMs: 60_000,
  tokenVerifyTimeoutMs: 10_000,
  readPageChars: 40_000,
});

export const DEFAULTS = Object.freeze({
  port: 8090,
  siteUrl: 'https://strido.cortex.a2olabs.com',
  model: 'claude-sonnet-5',
  quotaBytes: 200 * 1024 * 1024,
});

export class ConfigError extends Error {}

/** Trimmed value of a variable, or '' when unset. */
function read(env, name) {
  return (env[name] ?? '').trim();
}

function port(value) {
  if (value === '') return DEFAULTS.port;
  const number = Number(value);
  if (!Number.isInteger(number) || number < 1 || number > 65_535) throw new ConfigError('PORT must be 1..65535');
  return number;
}

/** A positive whole number of bytes, or the default when unset. */
function bytes(value, name, fallback) {
  if (value === '') return fallback;
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 1) throw new ConfigError(`${name} must be a positive number of bytes`);
  return number;
}

/** A base URL without its trailing slashes. */
function baseUrl(value, name) {
  if (value === '') return '';
  try {
    new URL(value);
  } catch {
    throw new ConfigError(`${name} is not a URL`);
  }
  return value.replace(/\/+$/, ''); // trailing slashes
}

/** Parse and check the environment. Throws `ConfigError` naming the variable at fault. */
export function loadConfig(env = process.env) {
  const knowledgeDir = read(env, 'KNOWLEDGE_DIR');
  if (knowledgeDir === '') throw new ConfigError('KNOWLEDGE_DIR is required (the synced docs-site/content tree)');

  const authMode = read(env, 'ASSISTANT_AUTH_MODE') || 'cortex';
  if (authMode !== 'cortex' && authMode !== 'dev') throw new ConfigError('ASSISTANT_AUTH_MODE must be cortex or dev');
  if (authMode === 'dev' && read(env, 'ASSISTANT_DEV') !== '1') {
    throw new ConfigError('ASSISTANT_AUTH_MODE=dev needs ASSISTANT_DEV=1 (it trusts every request)');
  }
  const headerSecret = read(env, 'CORTEX_APP_HEADER_SECRET');
  if (authMode === 'cortex' && headerSecret === '') {
    throw new ConfigError('CORTEX_APP_HEADER_SECRET is required with ASSISTANT_AUTH_MODE=cortex');
  }
  const directoryUrl = baseUrl(read(env, 'CORTEX_APP_DIRECTORY_URL'), 'CORTEX_APP_DIRECTORY_URL');
  const appKeyFile = read(env, 'CORTEX_APP_KEY_FILE');
  if ((directoryUrl === '') !== (appKeyFile === '')) {
    throw new ConfigError(`${directoryUrl === '' ? 'CORTEX_APP_DIRECTORY_URL' : 'CORTEX_APP_KEY_FILE'} is missing (both or neither)`);
  }

  const subscriber = read(env, 'CORTEX_MODEL_SUBSCRIBER').toLowerCase();
  return Object.freeze({
    port: port(read(env, 'PORT')),
    host: read(env, 'HOST') || '0.0.0.0',
    knowledgeDir: path.resolve(knowledgeDir),
    dataDir: path.resolve(read(env, 'ASSISTANT_DATA_DIR') || 'data'),
    quotaBytes: bytes(read(env, 'ASSISTANT_QUOTA_BYTES'), 'ASSISTANT_QUOTA_BYTES', DEFAULTS.quotaBytes),
    siteUrl: baseUrl(read(env, 'SITE_URL'), 'SITE_URL') || DEFAULTS.siteUrl,
    auth: Object.freeze({ mode: authMode, headerSecret, directoryUrl, appKeyFile }),
    model: Object.freeze({
      id: read(env, 'ASSISTANT_MODEL') || DEFAULTS.model,
      baseUrl: baseUrl(read(env, 'CORTEX_MODEL_BASE_URL') || read(env, 'ANTHROPIC_BASE_URL'), 'CORTEX_MODEL_BASE_URL'),
      subscriber,
      subscriberKey: read(env, 'CORTEX_MODEL_SUBSCRIBER_KEY'),
      sharedKey: subscriber === ''
        ? read(env, 'CORTEX_MODEL_KEY') || read(env, 'ANTHROPIC_API_KEY') || read(env, 'ANTHROPIC_AUTH_TOKEN')
        : read(env, 'CORTEX_MODEL_KEY'),
    }),
  });
}
