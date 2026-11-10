// Turning a docs page into what the assistant reads: front matter and Vue components removed, links
// made site-absolute, and the text split into sections at `##`/`###` with the heading ids the site uses.

import path from 'node:path/posix';

/** Matches YAML front matter at the very start of a file and captures its body. */
const FRONT_MATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;

/** Matches `<script …>…</script>` and `<style …>…</style>` blocks (Vue SFC parts in Markdown). */
const SCRIPT_OR_STYLE = /<(script|style)\b[^>]*>[\s\S]*?<\/\1>/g;

/** Matches a Vue component tag (opening, closing or self-closing): its name starts with a capital. */
const COMPONENT_TAG = /<\/?[A-Z][\w.-]*(\s[^<>]*)?\/?>/g;

/** Matches a custom container line `::: type Title` (captures type and title) or a closing `:::`. */
const CONTAINER = /^:::+\s*(\w*)\s*(.*)$/;

/** Matches the start or end of a fenced code block (``` or ~~~) and captures the fence. */
const FENCE = /^\s*(`{3,}|~{3,})/;

/** Matches an ATX heading of level 1-6 and captures the hashes and the text. */
const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;

/** Matches an explicit heading id `{#id}` at the end of the heading text and captures the id. */
const EXPLICIT_ID = /\s*\{#([^}\s]+)\}\s*$/;

/** Matches a Markdown link or image target `](target)` and captures the target. */
const LINK_TARGET = /\]\(([^)\s]+)(\s+"[^"]*")?\)/g;

/** Matches a URL with a scheme (`https:`, `mailto:`) or a protocol-relative one. */
const ABSOLUTE_URL = /^([a-z][a-z0-9+.-]*:|\/\/)/i;

/** Matches a `title:` line in front matter and captures the value (quotes optional). */
const FRONT_MATTER_TITLE = /^title:\s*["']?(.*?)["']?\s*$/m;

/** Matches blank-line runs of three or more newlines (left behind by removed components). */
const EXTRA_BLANK_LINES = /\n{3,}/g;

// The slug rule is copied from docs-site/scripts/slug.mjs (the service must not import from
// docs-site); keep both in step.

/** VitePress' heading slug, with en/em dashes as separators and stable `step-N` ids. */
export function slugify(text) {
  // "Step <number> – <title>" at the start of a heading (en dash, em dash or hyphen).
  const step = text.match(/^Step (\d+) [–—-] /);
  if (step) return `step-${step[1]}`;
  return text
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // combining accents left by NFKD
    .replace(/[\u0000-\u001f]/g, '') // control characters
    .replace(/[\s~`!@#$%^&*()\-_+=[\]{}|\\;:"'“”‘’<>,.?/–—]+/g, '-') // runs of spaces/punctuation/dashes -> one '-'
    .replace(/^-+|-+$/g, '') // no leading/trailing '-'
    .replace(/^(\d)/, '_$1') // ids must not start with a digit
    .toLowerCase();
}

/** The text VitePress slugs is the rendered heading: drop Markdown link targets and HTML tags first. */
export function headingText(markdown) {
  return markdown
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1') // [text](url) and ![alt](src) -> their text
    .replace(/<[^>]+>/g, '') // inline HTML tags
    .trim();
}

/** The site route of a content file: `docs/wiki/index.md` -> `/docs/wiki/`, `docs/a.md` -> `/docs/a`. */
export function routeOf(relativeFile) {
  const route = `/${relativeFile.replace(/\.md$/, '')}`; // drop the extension
  return route.endsWith('/index') ? route.slice(0, -'index'.length) : route;
}

/** A link target as the site path it opens (relative `.md` links resolved against the page). */
function siteLink(target, route) {
  if (ABSOLUTE_URL.test(target) || target.startsWith('#')) return target;
  const hashAt = target.indexOf('#');
  const file = hashAt === -1 ? target : target.slice(0, hashAt);
  const hash = hashAt === -1 ? '' : target.slice(hashAt);
  const directory = route.endsWith('/') ? route : path.dirname(route);
  let resolved = file.startsWith('/') ? file : path.join(directory, file);
  if (resolved.endsWith('.md')) resolved = routeOf(resolved.slice(1));
  return resolved + hash;
}

/**
 * Parse a page.
 * @returns {{title: string, markdown: string, sections: {id: string, title: string, level: number, text: string}[]}}
 *   `sections[0]` is the introduction (id '', the page title); the others follow `##` and `###` headings.
 */
export function parsePage(source, route) {
  const front = FRONT_MATTER.exec(source);
  const frontTitle = front === null ? '' : FRONT_MATTER_TITLE.exec(front[1])?.[1] ?? '';
  const body = (front === null ? source : source.slice(front[0].length))
    .replace(SCRIPT_OR_STYLE, '')
    .replace(COMPONENT_TAG, '');

  const lines = [];
  const sections = [];
  const used = new Map();
  let title = frontTitle;
  let current = { id: '', title: '', level: 1, lines: [] };
  let fence = null;

  const uniqueId = (id) => {
    // markdown-it-anchor's rule: the second "x" becomes "x-1", the third "x-2".
    const seen = used.get(id) ?? 0;
    used.set(id, seen + 1);
    return seen === 0 ? id : `${id}-${seen}`;
  };

  for (const raw of body.split(/\r?\n/)) { // lines
    let line = raw;
    const fenceMark = FENCE.exec(line);
    if (fence !== null) {
      if (fenceMark !== null && fenceMark[1][0] === fence[0] && fenceMark[1].length >= fence.length) fence = null;
    } else if (fenceMark !== null) {
      fence = fenceMark[1];
    } else {
      const container = CONTAINER.exec(line);
      if (container !== null) {
        if (container[2] === '') continue;
        line = `**${container[2]}**`;
      }
      const heading = HEADING.exec(line);
      if (heading !== null) {
        const level = heading[1].length;
        const explicit = EXPLICIT_ID.exec(heading[2]);
        const text = headingText(explicit === null ? heading[2] : heading[2].slice(0, explicit.index));
        const id = uniqueId(explicit?.[1] ?? slugify(text));
        line = `${heading[1]} ${text}`;
        if (level === 1 && title === '') title = text;
        if (level === 2 || level === 3) {
          sections.push(current);
          current = { id, title: text, level, lines: [] };
        }
      }
      line = line.replace(LINK_TARGET, (match, target, label = '') => `](${siteLink(target, route)}${label})`);
    }
    lines.push(line);
    current.lines.push(line);
  }
  sections.push(current);
  if (title === '') title = route;
  sections[0].title = title;

  return {
    title,
    markdown: lines.join('\n').replace(EXTRA_BLANK_LINES, '\n\n').trim(),
    sections: sections
      .map(({ id, title: heading, level, lines: own }) => ({
        id,
        title: heading,
        level,
        text: own.join('\n').replace(EXTRA_BLANK_LINES, '\n\n').trim(),
      }))
      .filter((section) => section.id !== '' || section.text !== ''),
  };
}
