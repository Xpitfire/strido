// Parts search over the site's runtime data: the purchased parts of the shop (`public/bom/shop.json`
// with `products.json`, plan A's offer) and the printed parts of the catalogue (`public/catalog/
// parts.json` with `products.json`). German variants are the `*.de.json` files.

import { readFileSync } from 'node:fs';
import path from 'node:path';

const MAX_RESULTS = 10;
const MAX_SPECS = 8;
const NAME_WEIGHT = 3;

/** Matches combining marks left by NFKD normalisation (accents), so "Schütz" matches "schutz". */
const COMBINING = /[\u0300-\u036f]/g;

/** Matches a run of letters or digits: the words of a query. */
const WORD = /[\p{L}\p{N}]+/gu;

function fold(text) {
  return String(text).normalize('NFKD').replace(COMBINING, '').toLowerCase();
}

function readJson(file) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

/** The first few specs of a product, as an object. */
function keySpecs(specs) {
  return Object.fromEntries(Object.entries(specs ?? {}).slice(0, MAX_SPECS));
}

export class PartsCatalog {
  /** language -> [{entry, name, haystack}] */
  #entries = new Map();

  constructor(root) {
    for (const language of ['en', 'de']) this.#entries.set(language, this.#load(root, language));
  }

  #load(root, language) {
    const suffix = language === 'de' ? '.de.json' : '.json';
    const prefix = language === 'de' ? '/de' : '';
    const shop = readJson(path.join(root, 'public/bom', `shop${suffix}`)) ?? readJson(path.join(root, 'public/bom/shop.json'));
    const products = readJson(path.join(root, 'public/bom', `products${suffix}`)) ?? readJson(path.join(root, 'public/bom/products.json'));
    const catalog = readJson(path.join(root, 'public/catalog', `parts${suffix}`)) ?? readJson(path.join(root, 'public/catalog/parts.json'));
    const entries = [];

    const plans = Array.isArray(shop?.plans) ? shop.plans : [];
    const planA = plans.find((plan) => plan.letter === 'A') ?? plans[0];
    for (const line of Array.isArray(shop?.lines) ? shop.lines : []) {
      const product = products?.purchased?.[line.id] ?? {};
      const offer = line.offers?.[planA?.choice?.[line.id] ?? 0];
      const vendor = offer === undefined ? undefined : shop.vendors?.[offer.vendor];
      entries.push({
        entry: {
          id: line.id,
          kind: 'purchased',
          name: line.name,
          category: line.category,
          qty: line.qty,
          ...(offer === undefined ? {} : { price: offer.price, pack: offer.pack, shop: vendor?.name ?? offer.vendor }),
          summary: product.summary,
          role: product.role,
          specs: keySpecs(product.specs),
          path: `${prefix}/docs/shop#part=${line.id}`,
        },
        haystack: [line.id, line.category, product.summary, product.description, product.role, ...(product.features ?? []), ...Object.entries(product.specs ?? {}).flat()],
      });
    }
    for (const part of Array.isArray(catalog?.parts) ? catalog.parts : []) {
      if (part.kind !== 'printed') continue;
      const product = products?.printed?.[part.id] ?? {};
      entries.push({
        entry: {
          id: part.id,
          kind: 'printed',
          name: part.title,
          qty: part.qty,
          summary: product.summary,
          role: product.role,
          specs: keySpecs({ colour: part.colour, size_mm: part.bbox_mm?.join(' × '), supports: part.supports, steps: part.steps?.join(', ') }),
          path: `${prefix}/docs/print-kit#part=${part.id}`,
        },
        haystack: [part.id, part.colour, product.summary, product.description, product.role, ...(product.features ?? [])],
      });
    }
    return entries.map(({ entry, haystack }) => ({
      entry,
      name: fold(`${entry.id.replaceAll('_', ' ')} ${entry.name ?? ''}`),
      haystack: fold(haystack.filter((value) => value !== undefined && value !== null).join(' ')),
    }));
  }

  count(language = 'en') {
    return this.#entries.get(language)?.length ?? 0;
  }

  /** Matching parts, best first: every query word found in the name scores 3, elsewhere 1. */
  search(query, { language = 'en', base = '' } = {}) {
    const words = [...new Set(fold(query).match(WORD) ?? [])].filter((word) => word.length >= 2);
    if (words.length === 0) return [];
    return (this.#entries.get(language) ?? [])
      .map((candidate) => ({
        candidate,
        score: words.reduce(
          (sum, word) => sum + (candidate.name.includes(word) ? NAME_WEIGHT : candidate.haystack.includes(word) ? 1 : 0),
          0,
        ),
      }))
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, MAX_RESULTS)
      .map(({ candidate: { entry } }) => {
        const { path: route, ...rest } = entry;
        return { ...rest, url: `${base}${route}` };
      });
  }
}
