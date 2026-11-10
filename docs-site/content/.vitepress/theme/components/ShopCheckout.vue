<script setup lang="ts">
// Checkout per shop. No shop offers a public "fill my cart" link (Amazon's add-to-cart form only
// works for registered Associates), so each shop gets a guided checklist: "Open next item" opens the
// next unticked item's page in one reused tab per shop, shows the quantity and order code to enter,
// and ticks it; the copyable order list remains for shops with a quick-order form.
import { ref } from 'vue';
import { data, orderKey, orderList, setOrdered, shops, state, type CartRow, type ShopOrder } from '../shop/cart';
import { defineMessages, formatMoney, useLocale } from '../i18n';

const useMessages = defineMessages({
  en: {
    items: (count: number) => `${count} items`, plusShipping: '+ shipping', toFree: 'more for free shipping',
    inCart: (item: string, shop: string) => `${item} is in my ${shop} cart`, pack: (pack: number) => `pack of ${pack}`,
    next: 'Next:', setQuantity: (packs: number) => `— set the quantity to ${packs} in the shop, then add it to the cart.`,
    allTicked: (count: number, shop: string) => `All ${count} items are ticked: open the ${shop} cart and check out.`,
    openNext: (index: number, count: number) => `Open next item (${index}/${count})`, copied: 'Copied ✓', copy: 'Copy order list', reset: 'Reset',
  },
  de: {
    items: (count: number) => `${count} Artikel`, plusShipping: '+ Versand', toFree: 'fehlen bis zum Gratisversand',
    inCart: (item: string, shop: string) => `${item} liegt in meinem Warenkorb bei ${shop}`, pack: (pack: number) => `Packung zu ${pack}`,
    next: 'Als Nächstes:', setQuantity: (packs: number) => `– im Shop die Menge ${packs} einstellen und in den Warenkorb legen.`,
    allTicked: (count: number, shop: string) => `Alle ${count} Artikel sind abgehakt: Öffnen Sie den Warenkorb bei ${shop} und gehen Sie zur Kasse.`,
    openNext: (index: number, count: number) => `Nächsten Artikel öffnen (${index}/${count})`, copied: 'Kopiert ✓', copy: 'Bestellliste kopieren', reset: 'Zurücksetzen',
  },
});
const t = useMessages();
const locale = useLocale();

const copied = ref('');

const done = (row: CartRow) => state.ordered.includes(orderKey(row));
const doneCount = (shop: ShopOrder) => shop.rows.filter(done).length;
const nextRow = (shop: ShopOrder) => shop.rows.find((row) => !done(row));

function openNext(shop: ShopOrder) {
  const row = nextRow(shop);
  if (!row) return;
  // One named tab per shop: every click reuses it instead of piling up tabs (and passes popup blockers).
  window.open(row.offer.url, `strido-${shop.key}`);
  setOrdered(orderKey(row), true);
}

function reset(shop: ShopOrder) {
  for (const row of shop.rows) setOrdered(orderKey(row), false);
}

async function copyList(shop: ShopOrder) {
  await navigator.clipboard.writeText(orderList(shop));
  copied.value = shop.key;
  setTimeout(() => (copied.value = ''), 2000);
}
</script>

<template>
  <div v-if="data" class="yx-checkout">
    <article v-for="shop in shops" :key="shop.key" class="yx-checkout__shop">
      <header><h3>{{ shop.vendor.name }}</h3><strong>{{ formatMoney(shop.total, locale) }}</strong></header>
      <p class="yx-checkout__meta">{{ t.items(shop.rows.length) }} {{ formatMoney(shop.subtotal, locale) }} {{ t.plusShipping }} {{ formatMoney(shop.shipping, locale) }}<template v-if="shop.toFree > 0"> · {{ formatMoney(shop.toFree, locale) }} {{ t.toFree }}</template></p>
      <p v-if="shop.vendor.note" class="yx-checkout__note">{{ shop.vendor.note }}</p>
      <div class="yx-checkout__progress"><span :style="{ width: `${(100 * doneCount(shop)) / shop.rows.length}%` }" /></div>
      <ul>
        <li v-for="row in shop.rows" :key="row.line.id" :class="{ done: done(row) }">
          <input type="checkbox" :checked="done(row)" :aria-label="t.inCart(row.line.name, shop.vendor.name)" @change="setOrdered(orderKey(row), ($event.target as HTMLInputElement).checked)" />
          <span class="qty">{{ row.packs }}×</span>
          <span class="name"><a :href="row.offer.url" :target="`strido-${shop.key}`" @click="setOrdered(orderKey(row), true)">{{ row.line.name }}</a><small>{{ row.offer.code }}{{ row.offer.pack > 1 ? ` · ${t.pack(row.offer.pack)}` : '' }}</small></span>
          <span class="cost">{{ formatMoney(row.cost, locale) }}</span>
        </li>
      </ul>
      <p v-if="nextRow(shop)" class="yx-checkout__next">
        {{ t.next }} <strong>{{ nextRow(shop)!.packs }} × {{ nextRow(shop)!.line.name }}</strong> {{ t.setQuantity(nextRow(shop)!.packs) }}
      </p>
      <p v-else class="yx-checkout__next">{{ t.allTicked(shop.rows.length, shop.vendor.name) }}</p>
      <div class="yx-checkout__actions">
        <button v-if="nextRow(shop)" type="button" class="yx-btn yx-btn--primary" @click="openNext(shop)">{{ t.openNext(doneCount(shop) + 1, shop.rows.length) }}</button>
        <button type="button" class="yx-btn" @click="copyList(shop)">{{ copied === shop.key ? t.copied : t.copy }}</button>
        <button v-if="doneCount(shop)" type="button" class="yx-btn" @click="reset(shop)">{{ t.reset }}</button>
      </div>
    </article>
  </div>
</template>
