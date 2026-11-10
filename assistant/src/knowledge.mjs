// The knowledge base: the English and German docs pages of the synced content tree, split into
// sections and indexed with SQLite FTS5 (in memory, rebuilt at start-up). Answers search, page and
// sidebar questions for the chat model and the MCP tools alike.

import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

import { BOUNDS } from './config.mjs';
import { parsePage, routeOf } from './markdown.mjs';
import { PartsCatalog } from './parts.mjs';

/** Content subtrees that are the knowledge base, with their language. */
const ROOTS = [
  { dir: 'docs', lang: 'en' },
  { dir: 'requirements', lang: 'en' },
  { dir: 'de/docs', lang: 'de' },
  { dir: 'de/requirements', lang: 'de' },
];

const MAX_PAGES = 2000;
const MAX_PAGE_BYTES = 2 * 1024 * 1024;
const MAX_QUERY_TERMS = 16;
const MAX_SIDEBAR_DEPTH = 4;

/** Matches a run of letters or digits (any script): the words of a query. */
const WORD = /[\p{L}\p{N}]+/gu;

/** Matches the origin of an absolute URL (`https://host`) to reduce it to its path. */
const ORIGIN = /^[a-z][a-z0-9+.-]*:\/\/[^/]+/i;

/** Matches a trailing `.md` or `.html` extension of a page path. */
const PAGE_EXTENSION = /\.(md|html)$/;

/** FTS5 bm25 weights per column: lang, route, page title, section title, body (titles boosted). */
const BM25_WEIGHTS = '0.0, 0.0, 3.0, 5.0, 1.0';

/** An FTS5 query from free text: each word (2+ characters) as a quoted prefix term, OR-joined; '' if none. */
export function ftsQuery(text) {
  const words = [...new Set((String(text).toLowerCase().match(WORD) ?? []).filter((word) => word.length >= 2))];
  return words
    .slice(0, MAX_QUERY_TERMS)
    .map((word) => `"${word}"*`)
    .join(' OR ');
}

function* markdownFiles(directory, depth = 0) {
  if (depth > 8) return;
  let entries;
  try {
    entries = readdirSync(directory, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) yield* markdownFiles(full, depth + 1);
    else if (entry.isFile() && entry.name.endsWith('.md')) yield full;
  }
}

export class Knowledge {
  /** route -> {route, lang, title, markdown, sections} */
  pages = new Map();
  #db = new DatabaseSync(':memory:');
  #sidebar = {};
  #root;
  parts;

  constructor(root) {
    this.#root = root;
    this.#db.exec(
      `CREATE VIRTUAL TABLE sections USING fts5(
         lang UNINDEXED, route UNINDEXED, page_title, section_title, body, section_id UNINDEXED,
         tokenize = 'unicode61 remove_diacritics 2'
       )`,
    );
    this.#load();
    this.parts = new PartsCatalog(root);
  }

  #load() {
    const insert = this.#db.prepare(
      'INSERT INTO sections (lang, route, page_title, section_title, body, section_id) VALUES (?, ?, ?, ?, ?, ?)',
    );
    this.#db.exec('BEGIN');
    for (const { dir, lang } of ROOTS) {
      for (const file of markdownFiles(path.join(this.#root, dir))) {
        if (this.pages.size >= MAX_PAGES) break;
        if (statSync(file).size > MAX_PAGE_BYTES) continue;
        const route = routeOf(path.relative(this.#root, file).split(path.sep).join('/'));
        const page = { route, lang, ...parsePage(readFileSync(file, 'utf8'), route) };
        this.pages.set(route, page);
        for (const section of page.sections) {
          insert.run(lang, route, page.title, section.id === '' ? '' : section.title, section.text, section.id);
        }
      }
    }
    this.#db.exec('COMMIT');
    try {
      this.#sidebar = JSON.parse(readFileSync(path.join(this.#root, '.vitepress/generated.json'), 'utf8')).sidebar ?? {};
    } catch {
      this.#sidebar = {};
    }
  }

  counts() {
    const counts = { en: 0, de: 0 };
    for (const page of this.pages.values()) counts[page.lang] += 1;
    return counts;
  }

  /** The link of a page or section below `base` ('' for site-relative links, or the site URL). */
  static url(base, route, sectionId = '') {
    return `${base}${route}${sectionId === '' ? '' : `#${sectionId}`}`;
  }

  /** Ranked sections `{title, section, url, snippet}` for free text. */
  search(text, { language = 'en', limit = 5, base = '' } = {}) {
    const query = ftsQuery(text);
    if (query === '') return [];
    const rows = this.#db
      .prepare(
        `SELECT route, page_title, section_title, section_id,
                snippet(sections, 4, '**', '**', '…', 32) AS snippet
           FROM sections WHERE sections MATCH ? AND lang = ?
          ORDER BY bm25(sections, ${BM25_WEIGHTS}) LIMIT ?`,
      )
      .all(query, language, Math.max(1, Math.min(10, limit)));
    return rows.map((row) => ({
      title: row.page_title,
      section: row.section_title,
      url: Knowledge.url(base, row.route, row.section_id),
      snippet: row.snippet,
    }));
  }

  /** The route of a URL, path or content file name, or null when it names no page. */
  resolve(urlOrPath, language) {
    let pathname = String(urlOrPath).trim().replace(ORIGIN, '');
    const hashAt = pathname.search(/[#?]/); // start of the hash or query
    const hash = hashAt === -1 ? '' : pathname.slice(hashAt).replace(/^\?[^#]*/, ''); // drop a query
    if (hashAt !== -1) pathname = pathname.slice(0, hashAt);
    if (!pathname.startsWith('/')) pathname = `/${pathname}`;
    pathname = pathname.replace(PAGE_EXTENSION, '');
    if (pathname.endsWith('/index')) pathname = pathname.slice(0, -'index'.length);
    if (language === 'de' && !pathname.startsWith('/de/')) pathname = `/de${pathname}`;
    if (language === 'en' && pathname.startsWith('/de/')) pathname = pathname.slice('/de'.length);
    for (const candidate of [pathname, `${pathname}/`, pathname.replace(/\/$/, '')]) { // with and without trailing slash
      if (this.pages.has(candidate)) return { route: candidate, sectionId: hash.replace(/^#/, '') };
    }
    return null;
  }

  /**
   * A page's Markdown (or one section, by heading id, with its subsections), capped at 40k characters.
   * Returns `{title, url, markdown}` or null for an unknown page; an unknown section lists the ids.
   */
  readPage(urlOrPath, { section = '', language, base = '' } = {}) {
    const resolved = this.resolve(urlOrPath, language);
    if (resolved === null) return null;
    const page = this.pages.get(resolved.route);
    const sectionId = section || resolved.sectionId;
    let markdown = page.markdown;
    let title = page.title;
    if (sectionId !== '') {
      const start = page.sections.findIndex((candidate) => candidate.id === sectionId);
      if (start === -1) {
        const ids = page.sections.filter((s) => s.id !== '').map((s) => s.id).join(', ');
        return { title, url: Knowledge.url(base, page.route), markdown: `No section "${sectionId}" on this page. Sections: ${ids}` };
      }
      const level = page.sections[start].level;
      const end = page.sections.findIndex((candidate, index) => index > start && candidate.level <= level);
      markdown = page.sections.slice(start, end === -1 ? undefined : end).map((s) => s.text).join('\n\n');
      title = `${page.title} – ${page.sections[start].title}`;
    }
    const max = BOUNDS.readPageChars;
    if (markdown.length > max) {
      const ids = page.sections.filter((s) => s.id !== '').map((s) => s.id).join(', ');
      markdown = `${markdown.slice(0, max)}\n\n[Truncated: ${markdown.length - max} more characters. Read one section by id: ${ids}]`;
    }
    return { title, url: Knowledge.url(base, page.route, sectionId), markdown };
  }

  /** The sidebar of a language as `[{sidebar, sections: [{text, items: [{text, url, items?}]}]}]`. */
  listPages({ language = 'en', base = '' } = {}) {
    const keys = language === 'de' ? ['/de/', '/de/docs/wiki/'] : ['/', '/docs/wiki/'];
    const item = (entry, depth) => {
      const out = { text: String(entry.text ?? '') };
      if (typeof entry.link === 'string') out.url = /^https?:/.test(entry.link) ? entry.link : `${base}${entry.link}`; // already absolute
      if (Array.isArray(entry.items) && depth < MAX_SIDEBAR_DEPTH) out.items = entry.items.map((child) => item(child, depth + 1));
      return out;
    };
    return keys
      .filter((key) => Array.isArray(this.#sidebar[key]))
      .map((key) => ({ sidebar: Knowledge.url(base, key), sections: this.#sidebar[key].map((entry) => item(entry, 0)) }));
  }
}
