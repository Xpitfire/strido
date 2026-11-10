// Translation catalogue files (i18n/<locale>/<name>.json) and their command line:
//   node docs-site/scripts/i18n-catalogues.mjs extract   add new segments (de: null), drop unused ones
//   node docs-site/scripts/i18n-catalogues.mjs check     exit 1 while a segment lacks a translation or breaks the Markdown
//   node docs-site/scripts/i18n-catalogues.mjs status    coverage per catalogue
//   node docs-site/scripts/i18n-catalogues.mjs validate <file>...   structure check of one translator's files
import { mkdir, readFile, unlink, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DATA_FILES, I18N_ROOT, LOCALES, dataStrings, homeSegments, markdownSegments, segmentKey, translationOf } from './i18n.mjs';
import { filesBelow, publishedPages, repositoryPathOfPublic, repositoryRoot } from './pages.mjs';

// --------------------------------------------------------------------------- structure check

function tokens(text, pattern) {
  return (text.match(pattern) ?? []).sort();
}

export function translationProblems(english, translated) {
  // What a translation broke in the Markdown structure (code, math, links, HTML, table cells, lines).
  const problems = [];
  if (!translated.trim()) return ['empty'];
  const same = (name, pattern) => {
    if (JSON.stringify(tokens(english, pattern)) !== JSON.stringify(tokens(translated, pattern))) problems.push(`${name} differ`);
  };
  same('code spans', /`[^`]+`/g); // inline code
  same('math', /\$[^$\n]+\$/g); // inline math
  same('link targets', /\]\([^)]*\)/g); // ](target)
  same('HTML tags', /<\/?[A-Za-z!][^<>]*>/g); // tags with their attributes (a tag name follows '<', so '< 0.5 >' is no tag)
  same('bold markers', /\*\*/g); // ** emphasis
  if (/^\s*\|/.test(english) && (english.match(/(?<!\\)\|/g) ?? []).length !== (translated.match(/(?<!\\)\|/g) ?? []).length) {
    problems.push('table cells differ'); // unescaped pipes count the cells
  }
  if (english.split('\n').length !== translated.split('\n').length) problems.push('line count differs');
  return problems;
}

// --------------------------------------------------------------------------- catalogue files

export function catalogueFile(locale, name) {
  return path.join(I18N_ROOT, locale, `${name}.json`);
}

export async function readCatalogue(locale, name) {
  const text = await readFile(catalogueFile(locale, name), 'utf8').catch((error) => {
    if (error.code === 'ENOENT') return '{}';
    throw error;
  });
  return JSON.parse(text);
}

export function mergeCatalogue(previous, segments) {
  // Keep every translation still in use (in page order), add new segments untranslated, drop the rest.
  const next = {};
  for (const english of segments) {
    const key = segmentKey(english);
    if (next[key]) continue;
    const old = previous[key];
    next[key] = { en: english, de: translationOf(old, english) };
    const stale = typeof old?.de === 'string' ? old.de : old?.stale; // numbers moved: keep the old text for the translator
    if (next[key].de === null && stale) next[key].stale = stale;
  }
  return next;
}

async function writeCatalogue(locale, name, catalogue) {
  const file = catalogueFile(locale, name);
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, JSON.stringify(catalogue, null, 1) + '\n');
}

// --------------------------------------------------------------------------- command line

export async function catalogueSources() {
  // Every catalogue: {name, segments} for the published pages and the translated data files.
  const pages = await publishedPages();
  const data = [];
  for (const [publicPath, keys] of Object.entries(DATA_FILES)) {
    const value = JSON.parse(await readFile(path.join(repositoryRoot, repositoryPathOfPublic(publicPath)), 'utf8'));
    data.push({ name: `data/${publicPath}`, segments: dataStrings(value, keys) });
  }
  const home = await readFile(path.join(repositoryRoot, 'docs-site/content/index.md'), 'utf8');
  return [
    ...pages.map((page) => ({ name: page.repositoryPath, segments: markdownSegments(page.text) })),
    { name: 'site/home.md', segments: homeSegments(home) },
    ...data,
  ];
}

async function validateFile(file) {
  // Structure problems in one catalogue file (any path, e.g. a translator's working copy).
  const catalogue = JSON.parse(await readFile(file, 'utf8'));
  let count = 0;
  for (const [key, entry] of Object.entries(catalogue)) {
    if (typeof entry.de !== 'string') continue;
    const problems = translationProblems(entry.en, entry.de);
    if (problems.length) {
      count += 1;
      console.log(`${file} ${key}: ${problems.join(', ')}`);
    }
  }
  return count;
}

async function main(command) {
  const all = await catalogueSources();
  let missing = 0;
  let total = 0;
  let broken = 0;
  for (const locale of LOCALES) {
    const names = new Set(all.map(({ name }) => `${name}.json`));
    for (const file of await filesBelow(path.join(I18N_ROOT, locale))) { // catalogues of removed or renamed pages
      const name = path.relative(path.join(I18N_ROOT, locale), file).split(path.sep).join('/');
      if (names.has(name)) continue;
      if (command === 'extract') await unlink(file);
      else console.log(`${locale} ${name}: no published page or data file uses this catalogue (make i18n removes it)`);
    }
    for (const { name, segments } of all) {
      const previous = await readCatalogue(locale, name);
      const next = mergeCatalogue(previous, segments);
      // Every source segment, also the ones that share a key (same text, other numbers), must render.
      const unique = [...new Set(segments)];
      const open = unique.filter((english) => translationOf(next[segmentKey(english)], english) === null).length;
      missing += open;
      total += unique.length;
      if (command === 'extract') {
        if (JSON.stringify(previous) !== JSON.stringify(next)) await writeCatalogue(locale, name, next);
      } else if (open && (command === 'status' || command === 'check')) {
        console.log(`${locale} ${name}: ${open} of ${unique.length} segments untranslated`);
      }
      if (command === 'check') broken += await validateFile(catalogueFile(locale, name)).catch((error) => (error.code === 'ENOENT' ? 0 : Promise.reject(error)));
    }
  }
  console.log(`i18n: ${total - missing} of ${total} segments translated`);
  if (command === 'check' && broken) {
    console.error(`${broken} translations break the Markdown structure (listed above).`);
    process.exit(1);
  }
  if (command === 'check' && missing) {
    console.error('Untranslated segments: run `make i18n`, translate the entries with "de": null (i18n/README.md), then re-run the check.');
    process.exit(1);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [command = 'status', ...files] = process.argv.slice(2);
  if (command === 'validate') {
    let broken = 0;
    for (const file of files) broken += await validateFile(file);
    console.log(`${broken} broken translations in ${files.length} files`);
    process.exit(broken ? 1 : 0);
  }
  if (!['extract', 'check', 'status'].includes(command)) {
    console.error('usage: i18n-catalogues.mjs extract|check|status|validate <catalogue.json>...');
    process.exit(2);
  }
  await main(command);
}
