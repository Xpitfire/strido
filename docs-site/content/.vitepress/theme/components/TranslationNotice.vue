<script setup lang="ts">
// Note under the title of a German page that is only partly translated, with a link to the English
// original (the same route without the /de prefix).
import { computed } from 'vue';
import { useRoute } from 'vitepress';

const props = defineProps<{ missing: number; total: number }>();
const route = useRoute();
// '/de/docs/shop' -> '/docs/shop'; '/de/' -> '/'.
const englishPath = computed(() => route.path.replace(/^\/de(?=\/)/, ''));
</script>

<template>
  <div v-if="missing > 0" class="custom-block info yx-translation-notice">
    <p>
      Diese Seite ist teilweise übersetzt ({{ props.missing }} von {{ props.total }} Abschnitten noch auf Englisch).
      <a :href="englishPath" lang="en">Englische Originalseite lesen</a>
    </p>
  </div>
</template>

<style scoped>
.yx-translation-notice {
  margin: 12px 0 20px;
}
</style>
