// What the documentation site publishes: the canonical Markdown pages and the artefact trees, as
// repository paths. Shared by the sync step (sync-docs.mjs), the translation catalogues (i18n-catalogues.mjs)
// and the VitePress config.
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const repositoryRoot = path.dirname(siteRoot);
export const GITHUB_BLOB = 'https://github.com/Xpitfire/strido/blob/main';
export const SITE_URL = 'https://strido.cortex.a2olabs.com';
export const naturalOrder = new Intl.Collator('en', { numeric: true });

// Markdown trees mirrored at the same relative path (relative links keep working).
const PAGE_ROOTS = ['docs', 'requirements'];
// Single files published as pages: repository path -> page path inside content/.
const EXTRA_PAGES = { 'hardware/print/print_list.md': 'docs/hardware/print-list.md' };
// Binary artefacts served from the site root: repository directory -> public directory.
export const PUBLIC_TREES = {
  'docs/viewer': 'viewer', 'docs/catalog': 'catalog', 'docs/images': 'images', 'docs/assembly/img/parts': 'parts', 'docs/bom': 'bom',
  'hardware/print': 'print', 'docs/verification/data': 'data', 'docs/verification/logs': 'logs',
};

export function repositoryPathOfPublic(publicPath) {
  // 'bom/shop.json' -> 'docs/bom/shop.json'
  const [source, target] = Object.entries(PUBLIC_TREES).find(([, directory]) => publicPath.startsWith(`${directory}/`));
  return `${source}${publicPath.slice(target.length)}`;
}

export async function filesBelow(directory) {
  const entries = await readdir(directory, { withFileTypes: true }).catch((error) => {
    if (error.code === 'ENOENT') return [];
    throw error;
  });
  const files = [];
  for (const entry of entries.sort((a, b) => naturalOrder.compare(a.name, b.name))) {
    if (entry.name.startsWith('.')) continue;
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await filesBelow(absolute));
    else if (entry.isFile()) files.push(absolute);
  }
  return files;
}

export async function publishedPages() {
  // Every Markdown page: {repositoryPath, relative (path inside content/), source (absolute), text}.
  const pages = [];
  const add = async (source, relative) => {
    pages.push({ repositoryPath: path.relative(repositoryRoot, source).split(path.sep).join('/'), relative, source,
      text: await readFile(source, 'utf8') });
  };
  for (const root of PAGE_ROOTS) {
    for (const source of await filesBelow(path.join(repositoryRoot, root))) {
      if (!source.endsWith('.md')) continue;
      // README.md is the page of its directory: publish it as index.md (VitePress directory route)
      await add(source, path.relative(repositoryRoot, source).split(path.sep).join('/').replace(/(^|\/)README\.md$/i, '$1index.md'));
    }
  }
  for (const [source, relative] of Object.entries(EXTRA_PAGES)) await add(path.join(repositoryRoot, source), relative);
  return pages;
}

export async function publishedFiles() {
  // Every non-Markdown file below a page root (images next to the pages): {source, relative}.
  const files = [];
  for (const root of PAGE_ROOTS) {
    for (const source of await filesBelow(path.join(repositoryRoot, root))) {
      if (!source.endsWith('.md')) files.push({ source, relative: path.relative(repositoryRoot, source).split(path.sep).join('/') });
    }
  }
  return files;
}
