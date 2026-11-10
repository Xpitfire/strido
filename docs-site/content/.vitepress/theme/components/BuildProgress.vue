<script setup lang="ts">
// Build progress on the assembly manual: a "done" checkbox in every step heading (ids step-N, see
// slugify in config.mts) and a progress bar; ticks are remembered in this browser.
import { onMounted, ref } from 'vue';
import { onContentUpdated, useRoute } from 'vitepress';
import { defineMessages } from '../i18n';

const useMessages = defineMessages({
  en: {
    markDone: 'Mark this step as done',
    stepDone: (step: number) => `Step ${step} done`,
    progress: (done: number, total: number) => `${done} of ${total} steps done`,
    reset: 'reset',
  },
  de: {
    markDone: 'Diesen Schritt als erledigt markieren',
    stepDone: (step: number) => `Schritt ${step} erledigt`,
    progress: (done: number, total: number) => `${done} von ${total} Schritten erledigt`,
    reset: 'zurücksetzen',
  },
});
const t = useMessages();

const STORAGE_KEY = 'yx-build-progress';
// The assembly manual in either language: '/docs/assembly' or '/de/docs/assembly', optional trailing slash.
const ASSEMBLY_ROUTE = /^(\/de)?\/docs\/assembly\/?$/;
const route = useRoute();
const total = ref(0);
const done = ref<number[]>([]);
const active = ref(false);

function save() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(done.value));
  } catch {
    // storage blocked: progress lasts for this page view only
  }
}

function decorate() {
  active.value = ASSEMBLY_ROUTE.test(route.path);
  if (!active.value) return;
  try {
    done.value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]');
  } catch {
    done.value = [];
  }
  const headings = [...document.querySelectorAll<HTMLHeadingElement>('.vp-doc h2[id^="step-"]')];
  total.value = headings.length;
  for (const heading of headings) {
    if (heading.querySelector('.yx-step-done')) continue;
    const step = Number(heading.id.slice('step-'.length));
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.className = 'yx-step-done';
    box.title = t.value.markDone;
    box.setAttribute('aria-label', t.value.stepDone(step));
    box.checked = done.value.includes(step);
    heading.classList.toggle('yx-step--done', box.checked);
    box.addEventListener('change', () => {
      done.value = box.checked ? [...new Set([...done.value, step])] : done.value.filter((n) => n !== step);
      heading.classList.toggle('yx-step--done', box.checked);
      save();
    });
    heading.prepend(box);
  }
}

function reset() {
  done.value = [];
  save();
  for (const box of document.querySelectorAll<HTMLInputElement>('.yx-step-done')) {
    box.checked = false;
    box.closest('h2')?.classList.remove('yx-step--done');
  }
}

onMounted(decorate);
onContentUpdated(decorate);
</script>

<template>
  <div v-if="active && total" class="yx-progress" role="status">
    <div class="yx-progress__bar"><span :style="{ width: `${(100 * done.length) / total}%` }" /></div>
    <span>{{ t.progress(done.length, total) }}</span>
    <button v-if="done.length" type="button" @click="reset">{{ t.reset }}</button>
  </div>
</template>
