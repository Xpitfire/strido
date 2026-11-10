// Safe rendering of assistant answers: Markdown (marked, GFM) -> HTML sanitized by a private DOMPurify
// instance -> KaTeX math and code copy buttons added in the DOM. Model output may contain anything, so
// images, forms and styles are dropped, external links open in a new tab and site pages are marked
// for in-place navigation. Browser-only.
import createDOMPurify, { type DOMPurify } from 'dompurify';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { Marked } from 'marked';

/** Attribute carrying the route of a link to a page of this site. */
export const INTERNAL_LINK_ATTR = 'data-yx-internal';
/** At most this many formulas are typeset per message; further ones stay as source text. */
const MAX_FORMULAS = 300;
const PLACEHOLDER_OPEN = '\uE000';
const PLACEHOLDER_CLOSE = '\uE001';
const LITERAL_OPEN = '\uE002';
const LITERAL_CLOSE = '\uE003';

/*
 * Spans whose `$` must stay as written, set aside before math is looked for: fenced code (``` or ~~~ up
 * to the same fence or the end), inline code (`...` on one line), a link destination `](url "title")`
 * (one level of parentheses inside the url), and an autolink <scheme:...>.
 */
const LITERAL = /```[\s\S]*?(?:```|$)|~~~[\s\S]*?(?:~~~|$)|`[^`\n]+`|\]\((?:[^()\s]|\([^()\s]*\))*(?:\s+"[^"\n]*")?\)|<[a-z][a-z0-9+.-]*:[^<>\s]*>/gi;
/*
 * Math, never across a set-aside span (\uE002 starts one): 1 display $$...$$ (may span lines), or
 * 2 inline $...$: not after a backslash, no space right inside the dollars, single line, not followed
 * by a digit (so "$5 and $10" stays money).
 */
const MATH = /\$\$([^\uE002]+?)\$\$|(?<!\\)\$(?=\S)((?:\\.|[^\\$\n\uE002])+?)(?<=\S)\$(?!\d)/g;
/** Private-use characters the placeholders are built from, removed from model text first. */
const PLACEHOLDER_CHARS = /[\uE000-\uE003]/g;
/** A formula placeholder in text: private-use delimiters around its index. */
const PLACEHOLDER = /\uE000(\d+)\uE001/g;
/** A set-aside literal span: private-use delimiters around its index. */
const LITERAL_PLACEHOLDER = /\uE002(\d+)\uE003/g;
/** A path ending in a file extension other than .html (downloads, data files). */
const FILE_PATH = /\.(?!html$)[a-z0-9]+$/i;
/** Paths served by the assistant service, not by the site. */
const SERVICE_PATH = /^\/(api|mcp)(\/|$)/;

const marked = new Marked({ gfm: true, breaks: true, async: false });
let purifier: DOMPurify | null = null;

/** The route of a link to a page of this site, or null for other origins, files and service paths. */
export function internalRoute(href: string): string | null {
  let url: URL;
  try {
    url = new URL(href, window.location.href);
  } catch {
    return null;
  }
  if (url.origin !== window.location.origin || FILE_PATH.test(url.pathname) || SERVICE_PATH.test(url.pathname)) return null;
  return url.pathname + url.search + url.hash;
}

function sanitizer(): DOMPurify {
  if (purifier) return purifier;
  purifier = createDOMPurify(window);
  purifier.addHook('afterSanitizeAttributes', (node) => {
    if (node.nodeName !== 'A') return;
    node.removeAttribute(INTERNAL_LINK_ATTR); // only this hook may set it
    const route = internalRoute(node.getAttribute('href') ?? '');
    if (route) {
      node.setAttribute(INTERNAL_LINK_ATTR, route);
      node.removeAttribute('target');
    } else {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener noreferrer');
    }
  });
  return purifier;
}

/** Answer Markdown -> sanitized HTML for v-html. `copyLabel` labels the code copy buttons. */
export function renderMarkdown(source: string, copyLabel: string): string {
  const formulas: { tex: string; display: boolean; source: string }[] = [];
  const literals: string[] = [];
  const shielded = source
    .replace(PLACEHOLDER_CHARS, '')
    .replace(LITERAL, (match: string) => `${LITERAL_OPEN}${literals.push(match) - 1}${LITERAL_CLOSE}`)
    .replace(MATH, (match: string, display?: string, inline?: string) => {
      if (formulas.length >= MAX_FORMULAS) return match;
      formulas.push({ tex: (display ?? inline ?? '').trim(), display: display !== undefined, source: match });
      return `${PLACEHOLDER_OPEN}${formulas.length - 1}${PLACEHOLDER_CLOSE}`;
    })
    .replace(LITERAL_PLACEHOLDER, (_, index: string) => literals[Number(index)]);
  const html = sanitizer().sanitize(marked.parse(shielded) as string, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['img', 'picture', 'video', 'audio', 'style', 'form', 'input', 'button', 'textarea', 'select', 'iframe'],
    FORBID_ATTR: ['style'],
  });
  const template = document.createElement('template');
  template.innerHTML = html;
  if (formulas.length) typesetFormulas(template.content, formulas);
  for (const pre of template.content.querySelectorAll('pre')) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'yx-ai-copy';
    button.setAttribute('aria-label', copyLabel);
    button.title = copyLabel;
    pre.prepend(button);
  }
  return template.innerHTML;
}

/** Replaces placeholders with KaTeX output in text, and with the original source inside code or attributes. */
function typesetFormulas(root: DocumentFragment, formulas: { tex: string; display: boolean; source: string }[]) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  const texts: Text[] = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node instanceof Text) {
      if (node.data.includes(PLACEHOLDER_OPEN)) texts.push(node);
    } else if (node instanceof Element) {
      for (const attribute of node.attributes) {
        if (attribute.value.includes(PLACEHOLDER_OPEN)) {
          attribute.value = attribute.value.replace(PLACEHOLDER, (_, index: string) => formulas[Number(index)].source);
        }
      }
    }
  }
  for (const text of texts) {
    if (text.parentElement?.closest('code, pre')) {
      text.data = text.data.replace(PLACEHOLDER, (_, index: string) => formulas[Number(index)].source);
      continue;
    }
    const fragment = document.createDocumentFragment();
    let last = 0;
    for (const match of text.data.matchAll(PLACEHOLDER)) {
      fragment.append(text.data.slice(last, match.index));
      const formula = formulas[Number(match[1])];
      const holder = document.createElement('span');
      holder.className = formula.display ? 'yx-ai-math yx-ai-math--display' : 'yx-ai-math';
      katex.render(formula.tex, holder, { displayMode: formula.display, throwOnError: false, trust: false, strict: 'ignore', maxExpand: 500, maxSize: 50 });
      fragment.append(holder);
      last = match.index + match[0].length;
    }
    fragment.append(text.data.slice(last));
    text.replaceWith(fragment);
  }
}
