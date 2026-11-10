// Checking the attachments of a message before anything is stored: count, names, media types, sizes,
// and that the bytes are what they claim (image magic bytes, UTF-8 text).

import { LIMITS } from './config.mjs';
import { HttpError } from './http.mjs';

export const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif']);
export const TEXT_TYPES = new Set(['text/plain', 'text/markdown', 'text/csv', 'application/json', 'application/x-yaml', 'text/yaml']);

const MAX_NAME_CHARS = 200;

/** Matches a canonical base64 string (padding optional): only the alphabet, `=` only at the end. */
const BASE64 = /^[A-Za-z0-9+/]*={0,2}$/;

/** Matches control characters, which a file name shown in the UI must not carry. */
const CONTROL = /[\u0000-\u001f\u007f]/g;

/** Whether `data` starts like a file of `mediaType`. */
export function hasImageMagic(mediaType, data) {
  const ascii = (start, end) => data.subarray(start, end).toString('latin1');
  switch (mediaType) {
    case 'image/png':
      return data.length >= 8 && data.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
    case 'image/jpeg':
      return data.length >= 3 && data[0] === 0xff && data[1] === 0xd8 && data[2] === 0xff;
    case 'image/gif':
      return ascii(0, 6) === 'GIF87a' || ascii(0, 6) === 'GIF89a';
    case 'image/webp':
      return ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP';
    default:
      return false;
  }
}

const utf8 = new TextDecoder('utf-8', { fatal: true });

/** The validated attachments `[{name, mediaType, data: Buffer}]`, or an HttpError (400, 413, 415). */
export function parseAttachments(value) {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) throw new HttpError(400, 'invalid_request', 'attachments must be an array.');
  if (value.length > LIMITS.maxAttachments) {
    throw new HttpError(413, 'too_large', `At most ${LIMITS.maxAttachments} attachments per message.`);
  }
  return value.map((item, index) => {
    if (item === null || typeof item !== 'object') throw new HttpError(400, 'invalid_request', `attachments[${index}] must be an object.`);
    const { name, mediaType, data } = item;
    if (typeof name !== 'string' || name.trim() === '' || typeof mediaType !== 'string' || typeof data !== 'string') {
      throw new HttpError(400, 'invalid_request', `attachments[${index}] needs name, mediaType and data (base64).`);
    }
    const type = mediaType.toLowerCase().split(';')[0].trim();
    const image = IMAGE_TYPES.has(type);
    if (!image && !TEXT_TYPES.has(type)) {
      throw new HttpError(415, 'unsupported_media_type', `"${name}": images (PNG, JPEG, WebP, GIF) and text files only.`);
    }
    const limit = image ? LIMITS.maxImageBytes : LIMITS.maxTextBytes;
    // Base64 is 4 characters per 3 bytes: refuse an oversized one before decoding it.
    if (Math.floor((data.length * 3) / 4) - 2 > limit) {
      throw new HttpError(413, 'too_large', `"${name}" is larger than ${Math.round(limit / 1024)} KB.`);
    }
    if (!BASE64.test(data)) throw new HttpError(400, 'invalid_request', `"${name}": data is not base64.`);
    const bytes = Buffer.from(data, 'base64');
    if (bytes.length === 0) throw new HttpError(400, 'invalid_request', `"${name}" is empty.`);
    if (bytes.length > limit) throw new HttpError(413, 'too_large', `"${name}" is larger than ${Math.round(limit / 1024)} KB.`);
    if (image && !hasImageMagic(type, bytes)) {
      throw new HttpError(415, 'unsupported_media_type', `"${name}" is not a ${type.slice('image/'.length).toUpperCase()} image.`);
    }
    if (!image) {
      try {
        utf8.decode(bytes);
      } catch {
        throw new HttpError(415, 'unsupported_media_type', `"${name}" is not UTF-8 text.`);
      }
    }
    return { name: name.replace(CONTROL, '').trim().slice(0, MAX_NAME_CHARS), mediaType: type, data: bytes };
  });
}
