import { defineConfig } from 'vitepress';
import { statSync } from 'node:fs';
import path from 'node:path';
import generated from './generated.json' with { type: 'json' };
import { GITHUB_BLOB, PUBLIC_TREES, repositoryRoot, siteRoot } from '../../scripts/pages.mjs';
import { slugify } from '../../scripts/slug.mjs';
import { syncDocs } from '../../scripts/sync-docs.mjs';
import { germanSite } from './locale-de.mts';

const siteContent = path.join(siteRoot, 'content');

const DOCUMENT_SYNC_DEBOUNCE_MS = 120;
const SOURCES: Record<string, string> = generated.sources;
// Translated pages live under /<locale>/ and resolve their links against the English page.
const LOCALE_PREFIX = /^(de)\//; // content path of a translated page: "de/docs/..."
// repository path -> content path (English pages), to resolve links written against the repository layout
const CONTENT_OF: Record<string, string> = Object.fromEntries(
  Object.entries(SOURCES).filter(([content]) => !LOCALE_PREFIX.test(content)).map(([content, repo]) => [repo, content]));

function routeOf(contentPath: string): string {
  // Drop .md and map README/index pages onto their directory route.
  return '/' + contentPath.replace(/\.md$/i, '').replace(/(^|\/)(README|index)$/i, '$1');
}

function publicPathOf(repositoryPath: string): string | undefined {
  // Assets copied into public/ (catalogue PDF, viewer, images) are served by the site itself.
  const tree = Object.keys(PUBLIC_TREES).find((source) => repositoryPath.startsWith(`${source}/`));
  return tree ? `/${PUBLIC_TREES[tree]}${repositoryPath.slice(tree.length)}` : undefined;
}

export default defineConfig({
  title: 'Strido',
  description: 'Open 12-DoF quadruped: printable CAD, verified assembly, parts catalogue, firmware, ROS 2, simulation and training.',
  lang: 'en-US',
  locales: {
    root: { label: 'English', lang: 'en-US' },
    de: germanSite(generated.sidebar),
  },
  cleanUrls: true,
  srcExclude: ['public/**'],
  lastUpdated: false,
  appearance: true,
  head: [
    ['meta', { name: 'theme-color', content: '#1d2428' }],
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    // Apply the remembered outline toggle (theme/components/OutlineToggle.vue) before the first paint.
    ['script', {}, "try{if(localStorage.getItem('yx-outline-hidden')==='1')document.documentElement.classList.add('yx-outline-hidden')}catch(e){}"],
  ],
  themeConfig: {
    logo: '/favicon.svg',
    siteTitle: 'Strido',
    nav: [
      { text: 'Getting started', link: '/docs/getting-started' },
      { text: 'Shop', link: '/docs/shop' },
      { text: 'Print kit', link: '/docs/print-kit' },
      { text: '3D viewer', link: '/docs/viewer' },
      { text: 'Learn', link: '/docs/wiki/', activeMatch: '^/docs/wiki/' },
      {
        text: 'Docs',
        items: [
          { text: 'Parts catalogue', link: '/docs/catalog' },
          { text: 'Assembly manual', link: '/docs/assembly/' },
          { text: 'Electronics, wiring and power', link: '/docs/electronics' },
          { text: 'Software', link: '/docs/software' },
          { text: 'Simulation and learning', link: '/docs/simulation' },
          { text: 'Verification', link: '/docs/verification' },
          { text: 'Downloads', link: '/docs/downloads' },
          { text: 'AI assistant and agents', link: '/docs/ai' },
        ],
      },
    ],
    sidebar: generated.sidebar,
    outline: { level: [2, 3], label: 'On this page' },
    search: { provider: 'local', options: { detailedView: true, locales: { de: germanSite(generated.sidebar).search } } },
    socialLinks: [{ icon: 'github', link: 'https://github.com/Xpitfire/strido', ariaLabel: 'Source repository (private)' }],
    footer: {
      message: 'MIT licence. Mechanical design derived from Yertle by Jerome Graves. CAD, simulation and native tests are not hardware evidence — see <a href="/docs/verification">Verification</a>.',
      copyright: 'Strido',
    },
  },
  markdown: {
    lineNumbers: false,
    anchor: { slugify },
    math: true, // $…$ and $$…$$ rendered to SVG at build time (markdown-it-mathjax3): no client JavaScript
    headers: { slugify },
    config(md) {
      const originalFence = md.renderer.rules.fence!;
      md.renderer.rules.fence = (tokens, index, options, env, self) => {
        if (tokens[index].info.trim() === 'mermaid') {
          // Encode apostrophes so diagram source cannot terminate the HTML attribute.
          return `<MermaidDiagram encoded="${encodeURIComponent(tokens[index].content).replace(/'/g, '%27')}" />\n`;
        }
        return originalFence(tokens, index, options, env, self);
      };
      const originalLink = md.renderer.rules.link_open;
      md.renderer.rules.link_open = (tokens, index, options, env, self) => {
        const token = tokens[index];
        const href = token.attrGet('href');
        const page = typeof env.relativePath === 'string' ? SOURCES[env.relativePath] : undefined;
        const locale = typeof env.relativePath === 'string' ? env.relativePath.match(LOCALE_PREFIX)?.[1] : undefined;
        const localised = (route: string) => (locale ? `/${locale}${route}` : route);
        // A link whose text is its own URL (a bare or autolinked shop URL) reads as the shop's domain;
        // the full address stays in the href and the hover title.
        const text = tokens[index + 1];
        if (href && /^https?:\/\//i.test(href) && URL.canParse(href) && text?.type === 'text' && tokens[index + 2]?.type === 'link_close') {
          const shown = text.content.trim();
          if (shown === href || shown === href.replace(/^https?:\/\//i, '')) {
            text.content = new URL(href).hostname.replace(/^www\./, '');
            token.attrSet('title', href);
          }
        }
        // A site-root page link (/docs/..., /requirements/...) in a translated page goes to that language's page.
        if (href && locale && /^\/(docs|requirements)(\/|$|#)/.test(href)) token.attrSet('href', `/${locale}${href}`);
        // Rewrite relative links (no scheme, no leading '#' or '/') written against the repository tree.
        if (href && page && !/^(?:[a-z]+:|#|\/)/i.test(href)) {
          // Split the path from an optional query or fragment.
          const [pathname, suffix = ''] = href.split(/(?=[?#])/);
          const target = path.posix.normalize(path.posix.join(path.posix.dirname(page), decodeURI(pathname)));
          if (CONTENT_OF[target]) {
            token.attrSet('href', localised(routeOf(CONTENT_OF[target])) + suffix);
          } else if (publicPathOf(target)) {
            token.attrSet('href', publicPathOf(target) + suffix);
          } else if (!target.endsWith('.md') || !/^(docs|requirements)\//.test(target)) {  // repository files outside the site
            token.attrSet('href', `${GITHUB_BLOB}/${target}${suffix}`);
            token.attrSet('target', '_blank');
          }
        }
        return originalLink ? originalLink(tokens, index, options, env, self) : self.renderToken(tokens, index, options);
      };
    },
  },
  // Links to files served from public/ (STL, GLB, slicer profile, logs) are not pages: accept a site-root
  // link when it names an existing file; a missing file, a directory or a wrong page link stays dead.
  ignoreDeadLinks: [
    (url: string) => url.startsWith('/') && (statSync(path.join(siteContent, 'public', decodeURI(url)), { throwIfNoEntry: false })?.isFile() ?? false),
  ],
  vite: {
    // `make assistant` serves the assistant on 8090; the dev site reaches it like the gateway does in production.
    server: { host: '127.0.0.1', port: 4173, strictPort: true, fs: { allow: [repositoryRoot] },
      proxy: { '/api': 'http://127.0.0.1:8090', '/mcp': 'http://127.0.0.1:8090' } },
    preview: { host: '127.0.0.1', port: 4173, strictPort: true },
    build: { chunkSizeWarningLimit: 2600 },
    plugins: [{
      name: 'strido-canonical-documents',
      configureServer(server) {
        const sourceRoots = ['docs', 'requirements', 'hardware/print', 'i18n'].map((directory) => path.join(repositoryRoot, directory));
        server.watcher.add(sourceRoots);
        let timer: ReturnType<typeof setTimeout> | undefined;
        const onChange = (filename: string) => {
          if (!sourceRoots.some((root) => filename.startsWith(root + path.sep))) return;
          clearTimeout(timer);
          timer = setTimeout(() => {
            syncDocs().then(() => server.ws.send({ type: 'full-reload' })).catch((error: Error) => {
              server.config.logger.error(`Documentation sync failed: ${error.message}`);
            });
          }, DOCUMENT_SYNC_DEBOUNCE_MS);
        };
        server.watcher.on('add', onChange).on('change', onChange).on('unlink', onChange);
      },
    }],
  },
});
