// Copy the canonical Markdown (docs/, requirements/) and the published artefacts (renders,
// 3D viewer model, catalogue PDF, parts data) into the VitePress content tree, render every page in
// each further language from its translation catalogue (i18n.mjs), and build the sidebars.
// Everything this script writes is generated and git-ignored (docs-site/.gitignore).
import { mkdir, readFile, unlink, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { agentFiles } from './agent-files.mjs';
import { KIT_NAME, buildKit } from './build-kit.mjs';
import { readCatalogue } from './i18n-catalogues.mjs';
import { DATA_FILES, LOCALES, localiseLinks, translateData, translateHome, translateMarkdown } from './i18n.mjs';
import { PUBLIC_TREES, filesBelow, naturalOrder, publishedFiles, publishedPages, repositoryPathOfPublic, repositoryRoot, siteRoot } from './pages.mjs';

const contentRoot = path.join(siteRoot, 'content');

// Generated directories this script owns completely (stale files are deleted).
const OWNED = ['docs', 'requirements', ...LOCALES, ...LOCALES.map((locale) => `public/${locale}`), 'public/viewer', 'public/catalog', 'public/images', 'public/parts',
  'public/downloads', 'public/bom', 'public/print', 'public/data', 'public/logs'];

// Sidebar: ordered sections; an entry is an exact page or a directory prefix ending in '/'.
const SECTIONS = [
  { text: 'Start here', entries: ['docs/overview.md', 'docs/getting-started.md', 'docs/downloads.md', 'docs/viewer.md', 'docs/ai.md'] },
  { text: 'Build', entries: ['docs/shop.md', 'docs/print-kit.md', 'docs/catalog.md', 'docs/hardware/print-list.md', 'docs/assembly/index.md',
    'docs/electronics.md', 'docs/bom/index.md', 'docs/bom/shopping_list.md', 'docs/design.md'] },
  { text: 'Program & run', entries: ['docs/software.md'] },
  { text: 'Simulate & train', entries: ['docs/simulation.md', 'docs/ntx-integration.md'] },
  { text: 'Learn', entries: [], link: { text: 'Learn: the engineering wiki', link: '/docs/wiki/' } },
  { text: 'Verification', collapsed: true, entries: ['docs/verification.md', 'docs/verification/'] },
  { text: 'Project', collapsed: true, entries: ['requirements/', 'docs/architecture.md', 'docs/decisions.md', 'docs/harness.md', 'docs/configuration.md'] },
];
// The Learn wiki has its own sidebar (pages under /docs/wiki/).
const LEARN_SECTIONS = [
  { text: 'Learn', entries: ['docs/wiki/index.md', 'docs/wiki/glossary.md'], link: { text: '← Back to the build docs', link: '/docs/getting-started' } },
  { text: 'Robotics theory', entries: ['docs/wiki/theory/frames-and-rotations.md', 'docs/wiki/theory/kinematics.md',
    'docs/wiki/theory/statics-and-dynamics.md', 'docs/wiki/theory/control.md', 'docs/wiki/theory/legged-locomotion.md',
    'docs/wiki/theory/state-estimation.md', 'docs/wiki/theory/reinforcement-learning.md'] },
  { text: 'Hardware', entries: ['docs/wiki/hardware/servos.md', 'docs/wiki/hardware/batteries.md', 'docs/wiki/hardware/power.md',
    'docs/wiki/hardware/microcontrollers.md', 'docs/wiki/hardware/buses.md', 'docs/wiki/hardware/sensors.md', 'docs/wiki/hardware/mechanics.md'] },
  { text: 'Software', entries: ['docs/wiki/software/linux-on-the-pi.md', 'docs/wiki/software/docker.md', 'docs/wiki/software/ros2.md',
    'docs/wiki/software/firmware.md', 'docs/wiki/software/kinematics-and-gaits.md', 'docs/wiki/software/simulation-and-rl.md',
    'docs/wiki/software/cad-as-code.md'] },
  { text: 'Making', entries: ['docs/wiki/making/3d-printing.md', 'docs/wiki/making/fasteners.md', 'docs/wiki/making/tools-and-workshop.md',
    'docs/wiki/making/strength.md', 'docs/wiki/making/cable-management.md', 'docs/wiki/making/safety.md'] },
];
// Sidebar labels per further language (the page titles come from the translated pages).
const SIDEBAR_LABELS = {
  de: {
    'Start here': 'Erste Schritte', Build: 'Bauen', 'Program & run': 'Programmieren & betreiben', 'Simulate & train': 'Simulieren & trainieren',
    Learn: 'Lernen', Verification: 'Verifikation', Project: 'Projekt', More: 'Mehr', 'Robotics theory': 'Robotik-Theorie',
    Hardware: 'Hardware', Software: 'Software', Making: 'Fertigung', 'Learn: the engineering wiki': 'Lernen: das Technik-Wiki',
    '← Back to the build docs': '← Zurück zur Bauanleitung',
  },
};

async function writeChanged(destination, value) {
  const previous = await readFile(destination).catch((error) => {
    if (error.code === 'ENOENT') return null;
    throw error;
  });
  const next = Buffer.isBuffer(value) ? value : Buffer.from(value);
  if (previous?.equals(next)) return;
  await mkdir(path.dirname(destination), { recursive: true });
  await writeFile(destination, next);
}

function titleOf(raw, filename) {
  // First level-1 Markdown heading, without trailing hashes or a {#id}.
  const heading = raw.match(/^#\s+(.+?)\s*(\{#[^}]+\})?\s*#*\s*$/m)?.[1];
  // Strip link syntax and inline emphasis/code markers from the title.
  return (heading || path.basename(filename, '.md').replace(/[-_]/g, ' ')).replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[`*_]/g, '');
}

function routeOf(relative) {
  // Drop the .md suffix and map README/index pages to their directory route.
  return '/' + relative.replace(/\.md$/i, '').replace(/(^|\/)(README|index)$/i, '$1');
}

function sectionOf(sections, page) {
  for (const [index, section] of sections.entries()) {
    const position = section.entries.findIndex((entry) => (entry.endsWith('/') ? page.source.startsWith(entry) : page.source === entry));
    if (position >= 0) return { index, position };
  }
  return null;
}

function sidebarOf(sectionList, pages, more, locale) {
  // Building sections start open; reference sections start collapsed (VitePress opens the section of
  // the current page). A section's fixed `link` item comes after its pages.
  const label = (text) => (locale ? SIDEBAR_LABELS[locale][text] ?? text : text);
  const prefix = locale ? `/${locale}` : '';
  const sections = sectionList.map((section) => ({ text: label(section.text), collapsed: Boolean(section.collapsed), items: [] }));
  const extra = { ...more, text: label(more.text), items: [] };
  const placed = pages.map((page) => ({ page, slot: sectionOf(sectionList, page) }))
    .sort((a, b) => (a.slot?.position ?? 0) - (b.slot?.position ?? 0) || naturalOrder.compare(a.page.source, b.page.source));
  for (const { page, slot } of placed) {
    if (slot) sections[slot.index].items.push({ text: page.title, link: prefix + page.route });
    else extra.items.push({ text: page.title, link: prefix + page.route });
  }
  sectionList.forEach((section, index) => section.link
    && sections[index].items.push({ text: label(section.link.text), link: prefix + section.link.link }));
  return [...sections.filter((section) => section.items.length), ...(extra.items.length ? [extra] : [])];
}

function sidebar(pages, locale) {
  const prefix = locale ? `/${locale}` : '';
  const wiki = pages.filter((page) => page.source.startsWith('docs/wiki/'));
  const rest = pages.filter((page) => !page.source.startsWith('docs/wiki/'));
  return {
    [`${prefix}/docs/wiki/`]: sidebarOf(LEARN_SECTIONS, wiki, { text: 'More', collapsed: false }, locale),
    [`${prefix}/`]: sidebarOf(SECTIONS, rest, { text: 'More', collapsed: true }, locale),
  };
}

function sharedAssets(markdown, relative, locale) {
  // Images next to a page stay in the English tree: point a translated page's relative image paths there.
  const back = path.posix.relative(path.posix.dirname(`${locale}/${relative}`), path.posix.dirname(relative)) || '.';
  // Absolute targets (scheme, site root, fragment) stay; a leading './' is dropped before prefixing.
  const shared = (target) => (/^(?:[a-z]+:|\/|#)/i.test(target) ? target : `${back}/${target.replace(/^\.\//, '')}`);
  return markdown
    .replace(/(!\[[^\]]*\]\()([^)\s]+)/g, (match, head, target) => head + shared(target)) // ![alt](target)
    .replace(/(<img\b[^>]*\bsrc=")([^"]+)/g, (match, head, target) => head + shared(target)); // <img src="target">
}

function withNotice(markdown, missing, total) {
  // A partly translated page says so under its title (theme component TranslationNotice).
  if (!missing) return markdown;
  const notice = `\n<TranslationNotice :missing="${missing}" :total="${total}" />\n`;
  const lines = markdown.split('\n');
  const title = lines.findIndex((line) => /^#\s/.test(line));
  if (title < 0) return `${notice}\n${markdown}`;
  lines.splice(title + 1, 0, notice);
  return lines.join('\n');
}

export async function syncDocs() {
  const expected = new Set();
  const write = async (relative, value) => {
    const destination = path.join(contentRoot, relative);
    await writeChanged(destination, value);
    expected.add(destination);
  };
  const pages = [];
  const sources = {};
  const translated = Object.fromEntries(LOCALES.map((locale) => [locale, []]));
  const texts = { en: [], ...Object.fromEntries(LOCALES.map((locale) => [locale, []])) }; // for the agent files
  const coverage = Object.fromEntries(LOCALES.map((locale) => [locale, { total: 0, missing: 0 }]));
  for (const page of await publishedPages()) {
    pages.push({ source: page.relative, title: titleOf(page.text, page.source), route: routeOf(page.relative) });
    texts.en.push({ route: routeOf(page.relative), relative: page.relative, title: titleOf(page.text, page.source), text: page.text });
    sources[page.relative] = page.repositoryPath;
    await write(page.relative, page.text);
    for (const locale of LOCALES) {
      const result = translateMarkdown(page.text, await readCatalogue(locale, page.repositoryPath));
      const text = withNotice(sharedAssets(localiseLinks(result.text, locale), page.relative, locale), result.missing, result.total);
      translated[locale].push({ source: page.relative, title: titleOf(text, page.source), route: routeOf(page.relative) });
      texts[locale].push({ route: `/${locale}${routeOf(page.relative)}`, relative: page.relative, title: titleOf(text, page.source), text });
      // A translated page resolves its relative links against the English page's repository path.
      sources[`${locale}/${page.relative}`] = page.repositoryPath;
      coverage[locale].total += result.total;
      coverage[locale].missing += result.missing;
      await write(`${locale}/${page.relative}`, text);
    }
  }
  for (const file of await publishedFiles()) await write(file.relative, await readFile(file.source));
  const home = await readFile(path.join(contentRoot, 'index.md'), 'utf8');
  for (const locale of LOCALES) {
    const result = translateHome(home, await readCatalogue(locale, 'site/home.md'));
    await write(`${locale}/index.md`, localiseLinks(result.text, locale));
  }
  for (const [sourceDirectory, publicDirectory] of Object.entries(PUBLIC_TREES)) {
    const root = path.join(repositoryRoot, sourceDirectory);
    for (const source of await filesBelow(root)) {
      if (source.endsWith('.md')) continue;
      await write(path.join('public', publicDirectory, path.relative(root, source)), await readFile(source));
    }
  }
  // Data the theme reads at runtime, per language: bom/products.json -> bom/products.de.json.
  for (const [publicPath, keys] of Object.entries(DATA_FILES)) {
    const value = JSON.parse(await readFile(path.join(repositoryRoot, repositoryPathOfPublic(publicPath)), 'utf8'));
    for (const locale of LOCALES) {
      const data = translateData(value, keys, await readCatalogue(locale, `data/${publicPath}`));
      await write(path.join('public', publicPath.replace(/\.json$/, `.${locale}.json`)), JSON.stringify(data));
    }
  }
  const kit = path.join(contentRoot, 'public', 'downloads', KIT_NAME);
  await writeChanged(kit, (await buildKit(repositoryRoot)).zip);
  expected.add(kit);
  const sidebars = Object.assign(sidebar(pages), ...LOCALES.map((locale) => sidebar(translated[locale], locale)));
  for (const [relative, data] of Object.entries(await agentFiles(texts, sidebars))) await write(path.join('public', relative), data);
  for (const directory of OWNED) {
    for (const generated of await filesBelow(path.join(contentRoot, directory))) {
      if (!expected.has(generated)) await unlink(generated);
    }
  }
  await writeChanged(path.join(contentRoot, '.vitepress/generated.json'),
    JSON.stringify({ sidebar: sidebars, sources, coverage }, null, 2) + '\n');
  return { pages: pages.length, coverage };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = await syncDocs();
  const languages = Object.entries(result.coverage).map(([locale, { total, missing }]) => `${locale} ${total - missing}/${total} segments`);
  console.log(`Synchronized ${result.pages} Strido documents (${languages.join(', ')}).`);
}
