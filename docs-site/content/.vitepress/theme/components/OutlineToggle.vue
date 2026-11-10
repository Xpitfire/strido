<script setup lang="ts">
// Collapses the "On this page" outline so wide tables (shopping list, print list, verification
// ledger) get the full width. The choice is remembered; an inline head script (config.mts) applies it
// before the first paint. Pages without an outline (frontmatter aside: false) get no toggle.
import { useData } from 'vitepress';
import { onMounted, ref } from 'vue';
import { defineMessages } from '../i18n';

const useMessages = defineMessages({
  en: { showTitle: 'Show the page outline', hideTitle: 'Hide the page outline (wider content)', show: '‹ Show outline', hide: 'Hide outline ›' },
  de: { showTitle: 'Seitenübersicht einblenden', hideTitle: 'Seitenübersicht ausblenden (breiterer Inhalt)', show: '‹ Übersicht einblenden', hide: 'Übersicht ausblenden ›' },
});
const t = useMessages();

const STORAGE_KEY = 'yx-outline-hidden';
const hidden = ref(false);
const { frontmatter } = useData();

function apply(value: boolean) {
  hidden.value = value;
  document.documentElement.classList.toggle('yx-outline-hidden', value);
  try {
    localStorage.setItem(STORAGE_KEY, value ? '1' : '0');
  } catch {
    // storage blocked (private mode): the toggle still works for this page view
  }
}

onMounted(() => {
  hidden.value = document.documentElement.classList.contains('yx-outline-hidden');
});
</script>

<template>
  <button
    v-if="frontmatter.aside !== false"
    type="button"
    class="yx-outline-toggle"
    :aria-pressed="hidden"
    :title="hidden ? t.showTitle : t.hideTitle"
    @click="apply(!hidden)"
  >
    {{ hidden ? t.show : t.hide }}
  </button>
</template>
