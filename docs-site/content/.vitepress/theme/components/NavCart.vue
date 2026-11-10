<script setup lang="ts">
// Cart indicator in the top bar on every page: number of robots and extra items in the shop cart
// (read from the cart's localStorage entry, kept in sync across tabs and with the shop page).
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vitepress';
import { cartCount, data } from '../shop/cart';
import { defineMessages, useLocalePath } from '../i18n';

const useMessages = defineMessages({
  en: { cart: (count: number) => `Cart: ${count} items` },
  de: { cart: (count: number) => `Warenkorb: ${count} Artikel` },
});
const t = useMessages();
const localePath = useLocalePath();

const STORAGE_KEY = 'yx-shop-cart';
const count = ref(0);
const route = useRoute();

function readStored() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null');
    const extras = Object.values((saved?.extras ?? {}) as Record<string, number>);
    count.value = (saved?.kits ?? 0) + extras.reduce((sum, n) => sum + n, 0);
  } catch {
    count.value = 0; // storage blocked or corrupt: show an empty cart
  }
}

// On the shop page the live cart state is authoritative; elsewhere the stored copy is.
watch([cartCount, () => route.path], () => (data.value ? (count.value = cartCount.value) : readStored()));
onMounted(() => {
  readStored();
  window.addEventListener('storage', readStored);
});
onBeforeUnmount(() => window.removeEventListener('storage', readStored));
</script>

<template>
  <a class="yx-nav-cart" :href="localePath('/docs/shop')" :aria-label="t.cart(count)" :title="t.cart(count)">
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M7 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM3 2h2.2l.9 2H21a1 1 0 0 1 .96 1.27l-2.6 9A1 1 0 0 1 18.4 15H8.1a1 1 0 0 1-.95-.68L4.6 4H3V2Zm4.06 4 1.8 7h8.78l2.02-7H7.06Z" /></svg>
    <span v-if="count">{{ count }}</span>
  </a>
</template>
