<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue';
import { useData } from 'vitepress';
import { defineMessages } from '../i18n';

const useMessages = defineMessages({
  en: {
    fitted: 'Fitted to the page width.', wide: 'Wide diagram: scroll sideways to explore.', actualSize: 'Actual size', fitWidth: 'Fit width',
    diagram: 'Diagram', rendering: 'Rendering diagram…', failed: 'Diagram could not render:', source: 'Diagram source',
  },
  de: {
    fitted: 'An die Seitenbreite angepasst.', wide: 'Breites Diagramm: seitlich scrollen.', actualSize: 'Originalgröße', fitWidth: 'An Breite anpassen',
    diagram: 'Diagramm', rendering: 'Diagramm wird gezeichnet…', failed: 'Diagramm konnte nicht gezeichnet werden:', source: 'Diagrammquelle',
  },
});
const t = useMessages();

// Below this scale diagram text drops under about 12 px, so wide diagrams scroll instead of shrinking.
const MIN_READABLE_SCALE = 0.75;
// Mermaid theme variables mirror the site tokens in style.css so diagrams match light and dark pages.
const DIAGRAM_THEMES = {
  light: {
    darkMode: false,
    background: '#fbfbf8',
    primaryColor: '#eef2dc',
    primaryTextColor: '#1d2428',
    primaryBorderColor: '#7f9a00',
    secondaryColor: '#f2f3ee',
    tertiaryColor: '#fbfbf8',
    textColor: '#1d2428',
    lineColor: '#4b555b',
    edgeLabelBackground: '#fbfbf8',
    noteBkgColor: '#fff4db',
    noteTextColor: '#1d2428',
    noteBorderColor: '#94610c',
  },
  dark: {
    darkMode: true,
    background: '#15191c',
    primaryColor: '#1c2125',
    primaryTextColor: '#e8ecee',
    primaryBorderColor: '#9cb316',
    secondaryColor: '#101315',
    tertiaryColor: '#15191c',
    textColor: '#e8ecee',
    lineColor: '#a9b3b8',
    edgeLabelBackground: '#15191c',
    noteBkgColor: '#332c20',
    noteTextColor: '#e8ecee',
    noteBorderColor: '#efc377',
  },
} as const;
const props = defineProps<{ encoded: string }>();
const { isDark } = useData();
const source = computed(() => decodeURIComponent(props.encoded));
const svg = ref('');
const error = ref('');
const rendering = ref(true);
const nativeWidth = ref(0);
const fitWidth = ref(false);
const overflows = ref(false);
const canvas = ref<HTMLElement | null>(null);
// Strip characters that cannot safely identify an SVG element.
const identifier = `strido-diagram-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
let generation = 0;
let disposed = false;
let resizeObserver: ResizeObserver | undefined;

// Recompute whether the diagram overflows its canvas; auto-fit only while the scale stays readable.
// A manual toggle is kept until the overflow state itself changes (for example after a resize).
function updateFit(): void {
  if (!canvas.value || nativeWidth.value <= 0) return;
  const style = getComputedStyle(canvas.value);
  const available = canvas.value.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  const nowOverflows = nativeWidth.value > available;
  if (nowOverflows === overflows.value) return;
  overflows.value = nowOverflows;
  fitWidth.value = nowOverflows && nativeWidth.value * MIN_READABLE_SCALE <= available;
}

onMounted(() => {
  watch([source, isDark], async () => {
    const current = ++generation;
    rendering.value = true;
    error.value = '';
    try {
      const { default: mermaid } = await import('mermaid');
      await document.fonts.ready;
      if (disposed || current !== generation) return;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        htmlLabels: false,
        theme: 'base',
        themeVariables: { ...(isDark.value ? DIAGRAM_THEMES.dark : DIAGRAM_THEMES.light), fontFamily: 'Arial, sans-serif' },
        layout: 'dagre',
        look: 'classic',
        fontFamily: 'Arial, sans-serif',
        fontSize: 16,
        flowchart: { useMaxWidth: false, wrappingWidth: 160, nodeSpacing: 30, rankSpacing: 64 },
        // wrapPadding 0 overprints wrapped lines in Mermaid 12.2; 2 keeps text inside lifelines.
        sequence: { useMaxWidth: false, wrap: true, width: 130, actorMargin: 50, wrapPadding: 2, messageMargin: 40 },
        // Mermaid's default 120 px state label width breaks words; minNodeWidth 0 keeps labels centred.
        state: { useMaxWidth: false, wrappingWidth: 220, minNodeWidth: 0 },
        suppressErrorRendering: true,
      });
      const result = await mermaid.render(`${identifier}-${current}`, source.value);
      if (!disposed && current === generation) {
        const image = new DOMParser().parseFromString(result.svg, 'image/svg+xml').documentElement;
        const viewBox = image.getAttribute('viewBox');
        if (!viewBox) throw new Error('Diagram has no measurable view box.');
        // SVG view-box values are separated by whitespace.
        const width = Number(viewBox.trim().split(/\s+/)[2]);
        if (!Number.isFinite(width) || width <= 0) throw new Error('Diagram width is invalid.');
        nativeWidth.value = width;
        svg.value = result.svg;
        await nextTick();
        overflows.value = false;
        fitWidth.value = false;
        updateFit();
        if (canvas.value && !resizeObserver) {
          resizeObserver = new ResizeObserver(updateFit);
          resizeObserver.observe(canvas.value);
        }
      }
    } catch (cause) {
      if (!disposed && current === generation) {
        svg.value = '';
        error.value = cause instanceof Error ? cause.message : String(cause);
      }
    } finally {
      if (!disposed && current === generation) rendering.value = false;
    }
  }, { immediate: true });
});
onBeforeUnmount(() => { disposed = true; generation += 1; resizeObserver?.disconnect(); });
</script>

<template>
  <figure class="yx-diagram" :aria-busy="rendering">
    <template v-if="svg">
      <div v-if="overflows" class="yx-diagram__toolbar">
        <span :id="`${identifier}-help`">{{ fitWidth ? t.fitted : t.wide }}</span>
        <button type="button" :aria-controls="`${identifier}-viewport`" @click="fitWidth = !fitWidth">
          {{ fitWidth ? t.actualSize : t.fitWidth }}
        </button>
      </div>
      <div
        :id="`${identifier}-viewport`"
        ref="canvas"
        class="yx-diagram__canvas"
        :class="{ 'yx-diagram__canvas--fit': fitWidth }"
        :style="{ '--diagram-width': `${nativeWidth}px` }"
        role="region"
        :aria-label="t.diagram"
        :aria-describedby="overflows ? `${identifier}-help` : undefined"
        tabindex="0"
        v-html="svg"
      />
    </template>
    <p v-if="rendering" class="yx-diagram__message" role="status">{{ t.rendering }}</p>
    <p v-if="error" class="yx-diagram__error" role="alert">{{ t.failed }} {{ error }}</p>
    <details v-if="error" open>
      <summary>{{ t.source }}</summary>
      <pre><code>{{ source }}</code></pre>
    </details>
  </figure>
</template>
