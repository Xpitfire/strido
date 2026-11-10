// Translation catalogues: every published English page (hand-written or generated) is split into
// segments (paragraphs, list items, table rows, headings, diagram sources); a catalogue per page in
// i18n/<locale>/<repository path>.json maps each segment to its translation. The German site is
// rendered from the current English page plus the catalogue, so a regenerated report keeps its
// translation, a changed number inside a translated sentence is carried over, and an English segment
// without a translation shows in English (the page then says it is partly translated).
//
// The catalogue files and the command line are in i18n-catalogues.mjs (`make i18n`).
import { createHash } from 'node:crypto';
import path from 'node:path';
import { repositoryRoot } from './pages.mjs';
import { headingText, slugify } from './slug.mjs';

export const I18N_ROOT = path.join(repositoryRoot, 'i18n');

// Further site languages (English is the source); each has catalogues in i18n/<locale>/ and pages under /<locale>/.
export const LOCALES = ['de'];

// Data files the theme reads at runtime: public path -> keys whose string values are translated.
export const DATA_FILES = {
  'bom/products.json': ['summary', 'description', 'features', 'role', 'specs'],
  'bom/shop.json': ['label', 'guide', 'category', 'note', 'name', 'region'],
  'catalog/parts.json': ['title'], // `colour` stays: it is a key the print kit groups by ('primary ...' / 'secondary ...')
  'viewer/assembly.json': ['title'],
};

// A number as written in English or German prose: 3, 0.71, 1,126.97, 0,71.
const NUMBER = /\d+(?:[.,]\d+)*/g;

// --------------------------------------------------------------------------- keys and lookup

export function segmentKey(english) {
  // Numbers do not take part in the key: a report whose figures change keeps its translations.
  return createHash('sha256').update(english.replace(NUMBER, '0')).digest('hex').slice(0, 16);
}

function germanNumber(token) {
  // 0.71 -> 0,71 and 1,126.97 -> 1.126,97: German swaps the decimal and the thousands separator.
  if (/^\d+\.\d+$/.test(token)) return token.replace('.', ','); // one decimal point
  if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(token)) return token.replace(/[.,]/g, (mark) => (mark === ',' ? '.' : ',')); // thousands groups
  return token;
}

export function translationOf(entry, english) {
  // The translation of `english`, with changed numbers carried over; null when there is none.
  if (!entry || typeof entry.de !== 'string') return null;
  if (entry.en === english) return entry.de;
  const before = entry.en.match(NUMBER) ?? [];
  const after = english.match(NUMBER) ?? [];
  if (before.length !== after.length) return null;
  // The translation keeps the numbers in the English order (the usual case, tables): replace by position,
  // in the style the translation wrote each number (German or English separators).
  const written = entry.de.match(NUMBER) ?? [];
  if (written.length === before.length && written.every((token, index) => token === before[index] || token === germanNumber(before[index]))) {
    let index = 0;
    return entry.de.replace(NUMBER, (token) => {
      const [old, next] = [before[index], after[index]];
      index += 1;
      // A number the translation kept in English notation (M2.5) stays English; otherwise German notation.
      return token === old && token !== germanNumber(old) ? next : germanNumber(next);
    });
  }
  const replace = new Map();
  for (const [index, old] of before.entries()) {
    for (const [from, to] of [[old, after[index]], [germanNumber(old), germanNumber(after[index])]]) {
      if (replace.has(from) && replace.get(from) !== to) return null; // one old number became two different ones
      replace.set(from, to);
    }
  }
  // A number in the translation that is none of the English ones (re-grouped, added) cannot be updated: retranslate.
  if (written.some((token) => !replace.has(token))) return null;
  return entry.de.replace(NUMBER, (token) => replace.get(token));
}

// --------------------------------------------------------------------------- Markdown segments

// Block starts that end a paragraph.
const FENCE = /^(\s*)(`{3,}|~{3,})(.*)$/; // ``` or ~~~ code fence with optional info string
const HEADING = /^(#{1,6})\s+(.*?)(?:\s+#+)?\s*(\{#[^}]+\})?\s*$/; // ATX heading, optional closing #s and {#id}
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])(\s+)(.*)$/; // bullet or numbered list item
const TABLE_ROW = /^\s*\|/; // a table row starts with a pipe
const TABLE_RULE = /^\s*\|?(\s*:?-{2,}:?\s*\|)+\s*:?-*:?\s*\|?\s*$/; // |---|:--:| separator row
const CONTAINER = /^(\s*:{3,})(\s*[\w-]+\s*)?(.*)$/; // ::: tip Title / ::: details / ::: v-pre / closing :::
const QUOTE = /^(\s*>\s?)(.*)$/; // blockquote line
const HTML_LINE = /^\s*<\/?[A-Za-z!]/; // a line that starts with an HTML tag or comment
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/; // horizontal rule
const LINK_DEFINITION = /^\s*\[[^\]]+\]:\s+\S/; // [label]: url

function startsBlock(line) {
  return FENCE.test(line) || HEADING.test(line) || LIST_ITEM.test(line) || TABLE_ROW.test(line) || CONTAINER.test(line)
    || QUOTE.test(line) || HTML_LINE.test(line) || line.trim() === '$$' || RULE.test(line);
}

export function hasProse(text) {
  // True when a segment holds words to translate, not only code, links, numbers and identifiers.
  const words = text
    .replace(/`[^`]*`/g, ' ') // inline code
    .replace(/\$[^$]*\$/g, ' ') // inline math
    .replace(/\]\([^)]*\)/g, '] ') // link targets
    .replace(/https?:\/\/\S+/g, ' ') // bare URLs
    .replace(/<[^>]+>/g, ' ') // HTML tags
    .match(/\p{L}[\p{L}'’-]*/gu) ?? []; // words: letters with inner apostrophes or hyphens
  return words.some((word) => word.length >= 3 && !/^(mm|cm|kg|min|mAh|kHz|MHz|GHz|AWG|USB|PCB|STL|GLB|PLA|PETG|TPU)$/.test(word));
}

export function segmentMarkdown(markdown) {
  // [{raw}] for verbatim lines, [{segment, prefix, linePrefix?, heading?, anchor?}] for text to translate.
  const lines = markdown.split('\n');
  const parts = [];
  const ids = new Set();
  const uniqueId = (base) => { // VitePress (markdown-it-anchor) numbers repeated heading ids: id, id-1, id-2 ...
    let id = base;
    for (let n = 1; ids.has(id); n += 1) id = `${base}-${n}`;
    ids.add(id);
    return id;
  };
  const raw = (line) => parts.push({ raw: line });
  const segment = (text, extra = {}) => {
    if (hasProse(text)) parts.push({ segment: text, prefix: '', ...extra });
    else parts.push({ raw: (extra.prefix ?? '') + (extra.linePrefix ? text.split('\n').map((l) => extra.linePrefix + l).join('\n') : text) + (extra.suffix ?? '') });
  };
  let index = 0;
  if (lines[0] === '---') { // front matter stays as it is
    const end = lines.indexOf('---', 1);
    if (end > 0) {
      for (; index <= end; index += 1) raw(lines[index]);
    }
  }
  while (index < lines.length) {
    const line = lines[index];
    const fence = line.match(FENCE);
    if (fence) {
      const [, , marker, info] = fence;
      const body = [];
      let close = index + 1;
      while (close < lines.length && !(lines[close].trim().startsWith(marker[0].repeat(marker.length)) && lines[close].trim().replace(/[`~]/g, '') === '')) {
        body.push(lines[close]);
        close += 1;
      }
      if (info.trim() === 'mermaid' && body.length) { // diagram labels are text to translate
        raw(line);
        segment(body.join('\n'));
        if (close < lines.length) raw(lines[close]);
      } else {
        for (let k = index; k <= Math.min(close, lines.length - 1); k += 1) raw(lines[k]);
      }
      index = close + 1;
      continue;
    }
    if (line.trim() === '$$') { // display math stays as it is
      let close = index + 1;
      while (close < lines.length && lines[close].trim() !== '$$') close += 1;
      for (let k = index; k <= Math.min(close, lines.length - 1); k += 1) raw(lines[k]);
      index = close + 1;
      continue;
    }
    if (/^\s*<!--/.test(line)) { // HTML comment, possibly over several lines
      let close = index;
      while (close < lines.length && !lines[close].includes('-->')) close += 1;
      for (let k = index; k <= Math.min(close, lines.length - 1); k += 1) raw(lines[k]);
      index = close + 1;
      continue;
    }
    if (line.trim() === '' || RULE.test(line) || LINK_DEFINITION.test(line) || TABLE_RULE.test(line) || /^\s*\$\$.*\$\$\s*$/.test(line)) {
      raw(line);
      index += 1;
      continue;
    }
    const heading = line.match(HEADING);
    if (heading) {
      const [, hashes, text, anchor] = heading;
      const id = anchor ?? `{#${uniqueId(slugify(headingText(text)))}}`;
      if (anchor) ids.add(anchor.slice(2, -1));
      if (hasProse(text)) parts.push({ segment: text, prefix: `${hashes} `, suffix: ` ${id}`, heading: true });
      else raw(`${hashes} ${text} ${id}`);
      index += 1;
      continue;
    }
    if (TABLE_ROW.test(line) || HTML_LINE.test(line)) {
      segment(line);
      index += 1;
      continue;
    }
    const container = line.match(CONTAINER);
    if (container) {
      const [, colons, kind = '', title] = container;
      if (title.trim()) parts.push(hasProse(title) ? { segment: title.trim(), prefix: `${colons}${kind}${kind.endsWith(' ') ? '' : ' '}` } : { raw: line });
      else raw(line);
      index += 1;
      continue;
    }
    const quote = line.match(QUOTE);
    if (quote) { // consecutive lines of one quote are one segment
      const prefix = quote[1];
      const body = [];
      while (index < lines.length && lines[index].startsWith(prefix) && lines[index].trim() !== prefix.trim()) {
        body.push(lines[index].slice(prefix.length));
        index += 1;
      }
      if (!body.length) {
        raw(line);
        index += 1;
        continue;
      }
      segment(body.join('\n'), { linePrefix: prefix });
      continue;
    }
    const item = line.match(LIST_ITEM);
    if (item) { // a list item with its continuation lines (indented deeper, not a new block)
      const [, indent, marker, gap, text] = item;
      const body = [text];
      index += 1;
      while (index < lines.length && lines[index].trim() !== '' && !startsBlock(lines[index])
        && lines[index].search(/\S/) > indent.length) {
        body.push(lines[index]);
        index += 1;
      }
      segment(body.join('\n'), { prefix: `${indent}${marker}${gap}` });
      continue;
    }
    const body = [line]; // paragraph
    index += 1;
    while (index < lines.length && lines[index].trim() !== '' && !startsBlock(lines[index])) {
      body.push(lines[index]);
      index += 1;
    }
    const indent = body[0].match(/^\s*/)[0];
    segment(body.map((l, k) => (k === 0 ? l.slice(indent.length) : l)).join('\n'), { prefix: indent });
  }
  return parts;
}

export function translateMarkdown(markdown, catalogue) {
  // The page in the target language: {text, total, missing}.
  let total = 0;
  let missing = 0;
  const lines = segmentMarkdown(markdown).map((part) => {
    if ('raw' in part) return part.raw;
    total += 1;
    let text = translationOf(catalogue[segmentKey(part.segment)], part.segment);
    if (text === null) {
      missing += 1;
      text = part.segment;
    }
    const body = part.linePrefix ? text.split('\n').map((line) => part.linePrefix + line).join('\n') : text;
    return part.prefix + body + (part.suffix ?? '');
  });
  return { text: lines.join('\n'), total, missing };
}

// --------------------------------------------------------------------------- home page and links

// A YAML text value of the home page front matter: "  tagline: ..." or "  - title: ...".
const FRONT_TEXT = /^(\s*(?:-\s+)?(?:text|tagline|alt|title|details|linkText|description):\s+)(.+)$/;

function splitFrontMatter(markdown) {
  const lines = markdown.split('\n');
  const end = lines[0] === '---' ? lines.indexOf('---', 1) : -1;
  return end > 0 ? { front: lines.slice(0, end + 1), body: lines.slice(end + 1).join('\n') } : { front: [], body: markdown };
}

export function homeSegments(markdown) {
  const { front, body } = splitFrontMatter(markdown);
  const values = front.map((line) => line.match(FRONT_TEXT)?.[2]).filter((value) => value && hasProse(value));
  return [...values, ...markdownSegments(body)];
}

export function translateHome(markdown, catalogue) {
  // The home page: front matter texts (hero, actions, features) and the body.
  const { front, body } = splitFrontMatter(markdown);
  let total = 0;
  let missing = 0;
  const lines = front.map((line) => {
    const match = line.match(FRONT_TEXT);
    if (!match || !hasProse(match[2])) return line;
    total += 1;
    const text = translationOf(catalogue[segmentKey(match[2])], match[2]);
    if (text === null) missing += 1;
    // A translated value with ": " or a leading YAML indicator must be quoted to stay one scalar.
    const value = text ?? match[2];
    return match[1] + (/: |^[\[{&*!|>'"%@`#-]/.test(value) ? JSON.stringify(value) : value);
  });
  const page = translateMarkdown(body, catalogue);
  return { text: [...lines, page.text].join('\n'), total: total + page.total, missing: missing + page.missing };
}

export function localiseLinks(markdown, locale) {
  // Site-root page links in HTML attributes and front matter (href="/docs/...", link: /docs/...) -> the locale's page.
  return markdown.replace(/(\bhref="|^\s*(?:-\s+)?link:\s+)\/(docs|requirements)(?=[/"#\s]|$)/gm, `$1/${locale}/$2`);
}

// --------------------------------------------------------------------------- JSON data

export function dataStrings(value, keys, inside = false, found = []) {
  // Every string under one of `keys` (nested arrays and objects included), in document order.
  if (typeof value === 'string') {
    if (inside && hasProse(value)) found.push(value);
  } else if (Array.isArray(value)) {
    for (const item of value) dataStrings(item, keys, inside, found);
  } else if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value)) dataStrings(item, keys, inside || keys.includes(key), found);
  }
  return found;
}

export function translateData(value, keys, catalogue, inside = false, counter = { total: 0, missing: 0 }) {
  if (typeof value === 'string') {
    if (!inside || !hasProse(value)) return value;
    counter.total += 1;
    const text = translationOf(catalogue[segmentKey(value)], value);
    if (text === null) counter.missing += 1;
    return text ?? value;
  }
  if (Array.isArray(value)) return value.map((item) => translateData(item, keys, catalogue, inside, counter));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, translateData(item, keys, catalogue, inside || keys.includes(key), counter)]));
  }
  return value;
}

export function markdownSegments(markdown) {
  return segmentMarkdown(markdown).filter((part) => 'segment' in part).map((part) => part.segment);
}
