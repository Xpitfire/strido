import DefaultTheme from 'vitepress/theme';
import type { Theme } from 'vitepress';
import { h } from 'vue';
import AiBar from './ai/AiBar.vue';
import AssemblyViewer from './components/AssemblyViewer.vue';
import BuildProgress from './components/BuildProgress.vue';
import MermaidDiagram from './components/MermaidDiagram.vue';
import NavCart from './components/NavCart.vue';
import OutlineToggle from './components/OutlineToggle.vue';
import PartsCatalog from './components/PartsCatalog.vue';
import PartsShop from './components/PartsShop.vue';
import PrintShop from './components/PrintShop.vue';
import TranslationNotice from './components/TranslationNotice.vue';
import './style.css';
import './store.css';

export default {
  extends: DefaultTheme,
  // Every documentation page gets the outline toggle (shown only where the outline is, >= 80rem) and
  // the build progress bar (shown only on the assembly manual); the top bar gets the cart indicator; every
  // page gets the AI assistant bar (theme/ai/).
  Layout: () =>
    h(DefaultTheme.Layout, null, {
      'doc-top': () => [h(OutlineToggle), h(BuildProgress)],
      'nav-bar-content-after': () => h(NavCart),
      'layout-bottom': () => h(AiBar),
    }),
  enhanceApp({ app }) {
    app.component('AssemblyViewer', AssemblyViewer);
    app.component('MermaidDiagram', MermaidDiagram);
    app.component('PartsCatalog', PartsCatalog);
    app.component('PartsShop', PartsShop);
    app.component('PrintShop', PrintShop);
    app.component('TranslationNotice', TranslationNotice);
  },
} satisfies Theme;
