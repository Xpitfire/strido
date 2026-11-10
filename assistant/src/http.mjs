// Small HTTP helpers shared by the routes: typed errors, JSON answers, bounded JSON bodies and the
// security headers every answer carries.

/** An error that becomes `{error: {code, message}}` with its status. */
export class HttpError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** Response headers for every route. The service serves data only, never HTML. */
export const SECURITY_HEADERS = Object.freeze({
  'content-security-policy': "default-src 'none'; frame-ancestors 'none'",
  'x-content-type-options': 'nosniff',
  'x-frame-options': 'DENY',
  'referrer-policy': 'no-referrer',
  'cross-origin-resource-policy': 'same-origin',
});

export function sendJson(res, status, body, headers = {}) {
  const text = JSON.stringify(body);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(text),
    'cache-control': 'no-store',
    ...headers,
  });
  res.end(text);
}

export function sendError(res, error) {
  if (res.headersSent) {
    res.destroy();
    return;
  }
  sendJson(res, error.status, { error: { code: error.code, message: error.message } });
}

/** Read a JSON body of at most `limit` bytes; 413 above it, 400 when it is not JSON. */
export async function readJson(req, limit) {
  const type = req.headers['content-type'] ?? '';
  if (!type.startsWith('application/json')) throw new HttpError(415, 'unsupported_media_type', 'Send application/json.');
  const declared = Number(req.headers['content-length'] ?? 0);
  if (declared > limit) throw new HttpError(413, 'too_large', 'The request is too large.');
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw new HttpError(413, 'too_large', 'The request is too large.');
    chunks.push(chunk);
  }
  if (size === 0) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw new HttpError(400, 'invalid_json', 'The body is not valid JSON.');
  }
}

/** A plain object, or a 400. */
export function expectObject(value, what = 'The body') {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new HttpError(400, 'invalid_request', `${what} must be a JSON object.`);
  }
  return value;
}
