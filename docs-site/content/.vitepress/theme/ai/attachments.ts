// Files attached to a question: accepted types, image downscaling and re-encoding in the browser,
// UTF-8 checks for text files, and base64 encoding for the request body. Browser-only (call from
// event handlers, never during server rendering).
import type { AttachmentUpload, Limits } from './useAssistantApi';

/** Long side of an image after downscaling, in pixels. */
const MAX_IMAGE_SIDE = 1600;
const JPEG_QUALITY = 0.85;
/** Larger source images are refused before decoding (keeps memory bounded). */
const MAX_SOURCE_IMAGE_BYTES = 40 * 1024 * 1024;

const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif']);
const TEXT_TYPES = new Set(['text/plain', 'text/markdown', 'text/csv', 'application/json', 'application/x-yaml', 'text/yaml']);
/** Browsers often report no or a vendor type for text files: the extension decides then. */
const TYPE_BY_EXTENSION: Record<string, string> = {
  txt: 'text/plain',
  log: 'text/plain',
  md: 'text/markdown',
  markdown: 'text/markdown',
  csv: 'text/csv',
  json: 'application/json',
  yaml: 'application/x-yaml',
  yml: 'application/x-yaml',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  webp: 'image/webp',
  gif: 'image/gif',
};

/** `accept` of the file picker. */
export const ACCEPT = [...IMAGE_TYPES, ...TEXT_TYPES, ...Object.keys(TYPE_BY_EXTENSION).map((ext) => `.${ext}`)].join(',');

export interface PendingAttachment extends AttachmentUpload {
  /** Local key for lists. */
  key: number;
  /** Bytes after encoding. */
  size: number;
  /** data: URL for image thumbnails. */
  previewUrl?: string;
}

export type AttachmentFailure = 'type' | 'image-size' | 'text-size' | 'encoding' | 'decode';

export class AttachmentError extends Error {
  constructor(
    readonly reason: AttachmentFailure,
    readonly fileName: string,
    readonly limit = 0,
  ) {
    super(`${fileName}: ${reason}`);
    this.name = 'AttachmentError';
  }
}

let nextKey = 1;

function mediaTypeOf(file: File): string | null {
  const type = file.type.toLowerCase();
  if (IMAGE_TYPES.has(type) || TEXT_TYPES.has(type)) return type;
  // The extension: the text after the last dot of the name.
  const extension = /\.([a-z0-9]+)$/i.exec(file.name)?.[1]?.toLowerCase();
  return extension ? (TYPE_BY_EXTENSION[extension] ?? null) : null;
}

/** Validates and encodes one file; throws AttachmentError with a reason a reader can act on. */
export async function prepareAttachment(file: File, limits: Limits): Promise<PendingAttachment> {
  const mediaType = mediaTypeOf(file);
  if (!mediaType) throw new AttachmentError('type', file.name);
  if (IMAGE_TYPES.has(mediaType)) return prepareImage(file, mediaType, limits);
  if (file.size > limits.maxTextBytes) throw new AttachmentError('text-size', file.name, limits.maxTextBytes);
  try {
    new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
  } catch {
    throw new AttachmentError('encoding', file.name);
  }
  const dataUrl = await readDataUrl(file);
  return { key: nextKey++, name: file.name, mediaType, data: base64Of(dataUrl), size: file.size };
}

async function prepareImage(file: File, sourceType: string, limits: Limits): Promise<PendingAttachment> {
  if (file.size > MAX_SOURCE_IMAGE_BYTES) throw new AttachmentError('image-size', file.name, limits.maxImageBytes);
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new AttachmentError('decode', file.name);
  }
  const scale = Math.min(1, MAX_IMAGE_SIDE / Math.max(bitmap.width, bitmap.height));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const surface = createSurface(width, height);
  surface.context.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();

  let blob: Blob | null = null;
  const transparent = sourceType !== 'image/jpeg' && hasTransparency(surface.context, width, height);
  if (transparent) {
    const png = await surface.encode('image/png');
    if (png.size <= limits.maxImageBytes) blob = png;
  }
  if (!blob) {
    if (transparent) {
      // JPEG has no alpha: paint white behind the image instead of letting it turn black.
      surface.context.globalCompositeOperation = 'destination-over';
      surface.context.fillStyle = '#fff';
      surface.context.fillRect(0, 0, width, height);
    }
    blob = await surface.encode('image/jpeg', JPEG_QUALITY);
  }
  if (blob.size > limits.maxImageBytes) throw new AttachmentError('image-size', file.name, limits.maxImageBytes);
  const dataUrl = await readDataUrl(blob);
  return {
    key: nextKey++,
    // Swap the extension (the text after the last dot) for the encoded format's.
    name: `${file.name.replace(/\.[^./]*$/, '') || 'image'}.${blob.type === 'image/png' ? 'png' : 'jpg'}`,
    mediaType: blob.type,
    data: base64Of(dataUrl),
    size: blob.size,
    previewUrl: dataUrl,
  };
}

type Context2D = OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;

interface Surface {
  context: Context2D;
  encode(type: string, quality?: number): Promise<Blob>;
}

/** An OffscreenCanvas where available, else a detached canvas element. */
function createSurface(width: number, height: number): Surface {
  if (typeof OffscreenCanvas !== 'undefined') {
    const canvas = new OffscreenCanvas(width, height);
    const context = canvas.getContext('2d');
    if (context) return { context, encode: (type, quality) => canvas.convertToBlob({ type, quality }) };
  }
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) throw new AttachmentError('decode', 'canvas');
  return {
    context,
    encode: (type, quality) => {
      const { promise, resolve, reject } = Promise.withResolvers<Blob>();
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('canvas encoding failed'))), type, quality);
      return promise;
    },
  };
}

function hasTransparency(context: Context2D, width: number, height: number): boolean {
  const pixels = context.getImageData(0, 0, width, height).data;
  for (let alpha = 3; alpha < pixels.length; alpha += 4) if (pixels[alpha] < 255) return true;
  return false;
}

function readDataUrl(blob: Blob): Promise<string> {
  const { promise, resolve, reject } = Promise.withResolvers<string>();
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result));
  reader.onerror = () => reject(reader.error ?? new Error('read failed'));
  reader.readAsDataURL(blob);
  return promise;
}

function base64Of(dataUrl: string): string {
  return dataUrl.slice(dataUrl.indexOf(',') + 1);
}
