<script setup lang="ts">
// Parts shop: the complete robot as one kit product, every part as a product card with its shop
// offers, a cart drawer and a guided checkout per shop (ShopCheckout.vue). State and pricing:
// ../shop/cart.ts.
import { computed, onMounted, ref } from 'vue';
import {
  KITS_MAX, addItem, addKit, cartCount, cartCsv, cartRows, clearCart, data, download, grandTotal, imageOf, itemsTotal,
  kitSummary, loadError, loadShop, offerLabel, offerOf, planOf, setKits, setOwned, shippingTotal, shops, state, usePlan,
  type Line,
} from '../shop/cart';
import { loadProducts, productInfo, stepsOf, strengthOf } from '../shop/products';
import ProductDialog from './ProductDialog.vue';
import ShopCheckout from './ShopCheckout.vue';
import { defineMessages, formatMoney, useLocale } from '../i18n';

const useMessages = defineMessages({
  en: {
    loadError: (error: string) => `Could not load the shop data (${error}).`, loading: 'Loading the shop…', heroAlt: 'Strido, assembled',
    completeKit: 'Complete kit', kitTitle: 'Strido — everything to build one robot',
    kitIntro: (count: number) => `All ${count} items: Raspberry Pi 5, ESP32-S3, 12 servos, LiDAR, camera, display, power electronics, bearings, every screw with spares and the filament. Choose how to buy:`,
    plan: 'Shopping plan', perRobot: (shops: number) => `per robot incl. shipping from ${shops} shops`, parts: 'parts', shipping: 'shipping',
    ownedLeftOut: (count: number) => ` · ${count} owned items left out`, added: 'Added ✓', addRobot: 'Add complete robot to cart',
    search: 'Search parts…', searchLabel: 'Search parts', categories: 'Categories', all: 'All', details: (name: string) => `Details: ${name}`,
    qtyPerRobot: (qty: number) => `${qty} per robot`, shopFor: (name: string) => `shop for ${name}`, pack: (pack: number) => ` / pack of ${pack}`,
    add: 'Add', owned: 'Already own it: leave out of the kit', checkout: 'Checkout: order per shop',
    empty: 'Your cart is empty. Add the complete robot or single parts above.',
    checkoutHint: (shops: number) => `The parts come from ${shops} shops. No shop offers a link that fills its cart from outside, so each shop has a checklist:`,
    openNext: 'Open next item',
    checkoutHint2: 'opens the next part\'s page in one reused tab per shop; set the quantity shown, add it to that shop\'s cart, come back and repeat. Shops with a quick-order form (DigiKey, Reichelt) also take the copied order list.',
    prices: (date: string) => `Prices EUR incl. VAT as observed ${date}, shipping to Austria. Shops change prices and stock: check each cart before paying.`,
    openCart: (count: number) => `Open cart, ${count} items`, cart: 'Cart', yourCart: 'Your cart', closeCart: 'Close cart', drawerEmpty: 'Empty. Start with the complete robot.',
    kitName: 'Strido complete kit', kitLine: (letter: string, items: number) => `Plan ${letter} · ${items} items ·`, partsEach: 'parts each',
    robotLess: 'one robot less', robotMore: 'one robot more', pieces: (pack: number) => ` / ${pack} pcs`, less: 'less', more: 'more',
    itemsLine: (lines: number) => `Items (${lines} lines, packs rounded up)`, shippingLine: (shops: number) => `Shipping (${shops} shops)`, total: 'Total',
    checkoutButton: 'Checkout per shop', downloadCsv: 'Download CSV', emptyCart: 'Empty cart', perRobotSpec: 'Per robot', addToCart: 'Add to cart',
    viewAt: (shop: string) => `View at ${shop}`, whereToBuy: 'Where to buy', shop: 'Shop', variant: 'Variant / code', price: 'Price', packSize: 'Pack',
    availability: 'Availability', clone: ' (clone)', listed: 'listed', view: 'view',
  },
  de: {
    loadError: (error: string) => `Die Shopdaten konnten nicht geladen werden (${error}).`, loading: 'Shop wird geladen…', heroAlt: 'Strido, zusammengebaut',
    completeKit: 'Kompletter Bausatz', kitTitle: 'Strido – alles für einen Roboter',
    kitIntro: (count: number) => `Alle ${count} Artikel: Raspberry Pi 5, ESP32-S3, 12 Servos, LiDAR, Kamera, Display, Leistungselektronik, Lager, jede Schraube mit Reserve und das Filament. Wählen Sie, wie Sie einkaufen:`,
    plan: 'Einkaufsplan', perRobot: (shops: number) => `pro Roboter inkl. Versand aus ${shops} Shops`, parts: 'Teile', shipping: 'Versand',
    ownedLeftOut: (count: number) => ` · ${count} vorhandene Artikel ausgelassen`, added: 'Hinzugefügt ✓', addRobot: 'Kompletten Roboter in den Warenkorb',
    search: 'Teile suchen…', searchLabel: 'Teile suchen', categories: 'Kategorien', all: 'Alle', details: (name: string) => `Details: ${name}`,
    qtyPerRobot: (qty: number) => `${qty} pro Roboter`, shopFor: (name: string) => `Shop für ${name}`, pack: (pack: number) => ` / Packung zu ${pack}`,
    add: 'Hinzufügen', owned: 'Schon vorhanden: aus dem Bausatz weglassen', checkout: 'Zur Kasse: Bestellung pro Shop',
    empty: 'Ihr Warenkorb ist leer. Legen Sie oben den kompletten Roboter oder einzelne Teile hinein.',
    checkoutHint: (shops: number) => `Die Teile kommen aus ${shops} Shops. Kein Shop bietet einen Link, der seinen Warenkorb von außen füllt, daher hat jeder Shop eine Checkliste:`,
    openNext: 'Nächsten Artikel öffnen',
    checkoutHint2: 'öffnet die Seite des nächsten Teils in einem wiederverwendeten Tab pro Shop; stellen Sie die angezeigte Menge ein, legen Sie das Teil in den Warenkorb dieses Shops, kehren Sie zurück und wiederholen Sie. Shops mit Schnellbestellformular (DigiKey, Reichelt) nehmen auch die kopierte Bestellliste an.',
    prices: (date: string) => `Preise in EUR inkl. USt., erhoben am ${date}, Versand nach Österreich. Shops ändern Preise und Lagerstand: Prüfen Sie jeden Warenkorb vor dem Bezahlen.`,
    openCart: (count: number) => `Warenkorb öffnen, ${count} Artikel`, cart: 'Warenkorb', yourCart: 'Ihr Warenkorb', closeCart: 'Warenkorb schließen', drawerEmpty: 'Leer. Beginnen Sie mit dem kompletten Roboter.',
    kitName: 'Strido kompletter Bausatz', kitLine: (letter: string, items: number) => `Plan ${letter} · ${items} Artikel ·`, partsEach: 'Teile je Roboter',
    robotLess: 'ein Roboter weniger', robotMore: 'ein Roboter mehr', pieces: (pack: number) => ` / ${pack} Stk.`, less: 'weniger', more: 'mehr',
    itemsLine: (lines: number) => `Artikel (${lines} Positionen, auf Packungen aufgerundet)`, shippingLine: (shops: number) => `Versand (${shops} Shops)`, total: 'Gesamt',
    checkoutButton: 'Zur Kasse pro Shop', downloadCsv: 'CSV herunterladen', emptyCart: 'Warenkorb leeren', perRobotSpec: 'Pro Roboter', addToCart: 'In den Warenkorb',
    viewAt: (shop: string) => `Bei ${shop} ansehen`, whereToBuy: 'Bezugsquellen', shop: 'Shop', variant: 'Variante / Code', price: 'Preis', packSize: 'Packung',
    availability: 'Verfügbarkeit', clone: ' (Nachbau)', listed: 'gelistet', view: 'ansehen',
  },
});
const t = useMessages();
const locale = useLocale();

const query = ref('');
const category = ref(''); // '' = all categories
const drawer = ref(false);
const added = ref('');
const detail = ref<Line | null>(null);

const DETAIL_HASH = '#part=';

onMounted(async () => {
  await Promise.all([loadShop(locale.value), loadProducts(locale.value)]);
  const id = location.hash.startsWith(DETAIL_HASH) ? decodeURIComponent(location.hash.slice(DETAIL_HASH.length)) : '';
  detail.value = data.value?.lines.find((line) => line.id === id) ?? null;
});

/** Opens the product page of a line; the URL hash makes it shareable (#part=<id>). */
function openDetail(line: Line | null) {
  detail.value = line;
  history.replaceState(history.state, '', line ? `${DETAIL_HASH}${encodeURIComponent(line.id)}` : location.pathname + location.search);
}

const categories = computed(() => ['', ...new Set(data.value?.lines.map((line) => line.category) ?? [])]);
const products = computed(() => {
  const needle = query.value.trim().toLowerCase();
  return (data.value?.lines ?? []).filter(
    (line) => (!category.value || line.category === category.value) && (!needle || line.name.toLowerCase().includes(needle)),
  );
});
const extraRows = computed(() => cartRows.value.filter((row) => row.extra > 0));
const plan = computed(() => planOf(state.plan));

function initials(line: Line) {
  return line.name.replace(/[^A-Za-z0-9 ]/g, ' ').split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join('').toUpperCase();
}

function flash(id: string) {
  added.value = id;
  setTimeout(() => (added.value = ''), 1200);
}

function addProduct(line: Line) {
  addItem(line.id, offerOf(line).pack);
  flash(line.id);
}

function addRobot() {
  addKit(1);
  flash('kit');
}

function downloadCsv() {
  download('strido-cart.csv', new Blob([cartCsv()], { type: 'text/csv' }));
}

function goToCheckout() {
  drawer.value = false;
  document.getElementById('checkout')?.scrollIntoView({ behavior: 'smooth' });
}
</script>

<template>
  <div class="yx-store">
    <p v-if="loadError" class="yx-store__error">{{ t.loadError(loadError) }}</p>
    <p v-else-if="!data">{{ t.loading }}</p>
    <template v-else>
      <!-- the complete robot -->
      <section class="yx-kit">
        <img src="/images/hero_front.png" :alt="t.heroAlt" class="yx-kit__image" />
        <div class="yx-kit__body">
          <span class="yx-badge">{{ t.completeKit }}</span>
          <h2 class="yx-kit__title">{{ t.kitTitle }}</h2>
          <p>{{ t.kitIntro(data.lines.length) }}</p>
          <div class="yx-kit__plans" role="radiogroup" :aria-label="t.plan">
            <button v-for="p in data.plans" :key="p.key" type="button" role="radio" :aria-checked="state.plan === p.key"
              :class="{ active: state.plan === p.key }" :title="p.guide" @click="usePlan(p.key)">
              <strong>{{ p.letter }}</strong> {{ p.label.split(' (')[0] }}
            </button>
          </div>
          <p class="yx-kit__guide">{{ plan?.guide }}</p>
          <div class="yx-kit__buy">
            <div class="yx-kit__price">{{ formatMoney(kitSummary.total, locale) }}<small>{{ t.perRobot(kitSummary.shops) }} ({{ formatMoney(kitSummary.parts, locale) }} {{ t.parts }} + {{ formatMoney(kitSummary.shipping, locale) }} {{ t.shipping }}){{ state.owned.length ? t.ownedLeftOut(state.owned.length) : '' }}</small></div>
            <button type="button" class="yx-btn yx-btn--primary" @click="addRobot">{{ added === 'kit' ? t.added : t.addRobot }}</button>
          </div>
        </div>
      </section>

      <!-- catalogue (the sticky toolbar ends with the grid) -->
      <section class="yx-store__catalogue">
      <div class="yx-store__toolbar">
        <input v-model="query" type="search" :placeholder="t.search" :aria-label="t.searchLabel" />
        <div class="yx-store__chips" role="group" :aria-label="t.categories">
          <button v-for="c in categories" :key="c" type="button" :class="{ active: category === c }" @click="category = c">{{ c || t.all }}</button>
        </div>
      </div>
      <div class="yx-store__grid">
        <article v-for="line in products" :key="line.id" class="yx-product" :class="{ owned: state.owned.includes(line.id) }">
          <button type="button" class="yx-product__image" :aria-label="t.details(line.name)" @click="openDetail(line)">
            <img v-if="imageOf(line)" :src="imageOf(line)!" :alt="line.name" loading="lazy" />
            <span v-else class="yx-product__glyph">{{ initials(line) }}</span>
          </button>
          <div class="yx-product__body">
            <span class="yx-product__category">{{ line.category }}</span>
            <h3><button type="button" class="yx-product__title" @click="openDetail(line)">{{ line.name }}</button></h3>
            <p v-if="productInfo?.purchased[line.id]" class="yx-product__summary">{{ productInfo.purchased[line.id].summary }}</p>
            <p class="yx-product__kit">{{ t.qtyPerRobot(line.qty) }}</p>
            <select v-model.number="state.choice[line.id]" :aria-label="t.shopFor(line.name)">
              <option v-for="(offer, index) in line.offers" :key="index" :value="index">
                {{ offerLabel(line, offer, locale) }}
              </option>
            </select>
            <p v-if="offerOf(line).stock" class="yx-product__stock">{{ offerOf(line).stock }}</p>
            <div class="yx-product__buy">
              <span class="yx-product__price">{{ formatMoney(offerOf(line).price, locale) }}<small v-if="offerOf(line).pack > 1">{{ t.pack(offerOf(line).pack) }}</small></span>
              <button type="button" class="yx-btn" @click="addProduct(line)">{{ added === line.id ? t.added : t.add }}</button>
            </div>
            <label class="yx-product__owned"><input type="checkbox" :checked="state.owned.includes(line.id)" @change="setOwned(line.id, ($event.target as HTMLInputElement).checked)" /> {{ t.owned }}</label>
          </div>
        </article>
      </div>
      </section>

      <!-- checkout -->
      <h2 id="checkout">{{ t.checkout }}</h2>
      <p v-if="!shops.length" class="yx-store__hint">{{ t.empty }}</p>
      <template v-else>
        <p class="yx-store__hint">{{ t.checkoutHint(shops.length) }} <strong>{{ t.openNext }}</strong> {{ t.checkoutHint2 }}</p>
        <ShopCheckout />
      </template>
      <p class="yx-store__hint">{{ t.prices(data.prices_observed) }}</p>

      <!-- cart -->
      <button type="button" class="yx-cart-fab" :aria-label="t.openCart(cartCount)" @click="drawer = true">
        🛒 <span>{{ cartCount }}</span> <strong>{{ formatMoney(grandTotal, locale) }}</strong>
      </button>
      <div v-if="drawer" class="yx-drawer__backdrop" @click="drawer = false" />
      <aside class="yx-drawer" :class="{ open: drawer }" :aria-label="t.cart">
        <header><h2>{{ t.yourCart }}</h2><button type="button" :aria-label="t.closeCart" @click="drawer = false">✕</button></header>
        <div class="yx-drawer__items">
          <p v-if="!cartRows.length" class="yx-store__hint">{{ t.drawerEmpty }}</p>
          <div v-if="state.kits" class="yx-cart-row yx-cart-row--kit">
            <img src="/images/hero_front.png" alt="" />
            <div><strong>{{ t.kitName }}</strong><small>{{ t.kitLine(plan?.letter ?? '', data.lines.length - state.owned.length) }} {{ formatMoney(kitSummary.parts, locale) }} {{ t.partsEach }}</small></div>
            <div class="yx-stepper">
              <button type="button" :aria-label="t.robotLess" @click="setKits(state.kits - 1)">−</button><span>{{ state.kits }}</span>
              <button type="button" :aria-label="t.robotMore" :disabled="state.kits >= KITS_MAX" @click="addKit(1)">+</button>
            </div>
          </div>
          <div v-for="row in extraRows" :key="row.line.id" class="yx-cart-row">
            <img v-if="imageOf(row.line)" :src="imageOf(row.line)!" alt="" />
            <span v-else class="yx-product__glyph yx-product__glyph--small">{{ initials(row.line) }}</span>
            <div><strong>{{ row.line.name }}</strong><small>{{ data.vendors[row.offer.vendor].name }} · {{ formatMoney(row.offer.price, locale) }}{{ row.offer.pack > 1 ? t.pieces(row.offer.pack) : '' }}</small></div>
            <div class="yx-stepper">
              <button type="button" :aria-label="t.less" @click="addItem(row.line.id, -row.offer.pack)">−</button><span>{{ row.extra }}</span>
              <button type="button" :aria-label="t.more" @click="addItem(row.line.id, row.offer.pack)">+</button>
            </div>
          </div>
        </div>
        <footer v-if="cartRows.length">
          <div class="yx-drawer__line"><span>{{ t.itemsLine(cartRows.length) }}</span><span>{{ formatMoney(itemsTotal, locale) }}</span></div>
          <div class="yx-drawer__line"><span>{{ t.shippingLine(shops.length) }}</span><span>{{ formatMoney(shippingTotal, locale) }}</span></div>
          <div class="yx-drawer__line yx-drawer__total"><span>{{ t.total }}</span><span>{{ formatMoney(grandTotal, locale) }}</span></div>
          <button type="button" class="yx-btn yx-btn--primary yx-btn--wide" @click="goToCheckout">{{ t.checkoutButton }}</button>
          <div class="yx-drawer__secondary">
            <button type="button" class="yx-btn" @click="downloadCsv">{{ t.downloadCsv }}</button>
            <button type="button" class="yx-btn" @click="clearCart">{{ t.emptyCart }}</button>
          </div>
        </footer>
      </aside>

      <!-- product page -->
      <ProductDialog
        v-if="detail"
        :title="detail.name"
        :category="detail.category"
        :image="imageOf(detail)"
        :glyph="initials(detail)"
        :info="productInfo?.purchased[detail.id]"
        :steps="stepsOf(detail.cad)"
        :strength="strengthOf(detail.id)"
        :specs="{ [t.perRobotSpec]: `${detail.qty}` }"
        @close="openDetail(null)"
      >
        <template #buy>
          <div class="yx-dialog__price">{{ formatMoney(offerOf(detail).price, locale) }}<small v-if="offerOf(detail).pack > 1">{{ t.pack(offerOf(detail).pack) }}</small></div>
          <select v-model.number="state.choice[detail.id]" :aria-label="t.shopFor(detail.name)">
            <option v-for="(offer, index) in detail.offers" :key="index" :value="index">
              {{ offerLabel(detail, offer, locale) }}
            </option>
          </select>
          <p v-if="offerOf(detail).stock" class="yx-product__stock">{{ offerOf(detail).stock }}</p>
          <p v-if="detail.note" class="yx-product__note">{{ detail.note }}</p>
          <div class="yx-dialog__actions">
            <button type="button" class="yx-btn yx-btn--primary" @click="addProduct(detail)">{{ added === detail.id ? t.added : t.addToCart }}</button>
            <a class="yx-btn" :href="offerOf(detail).url" target="_blank" rel="noreferrer">{{ t.viewAt(data.vendors[offerOf(detail).vendor].name) }}</a>
          </div>
          <label class="yx-product__owned"><input type="checkbox" :checked="state.owned.includes(detail.id)" @change="setOwned(detail.id, ($event.target as HTMLInputElement).checked)" /> {{ t.owned }}</label>
        </template>
        <template #details>
          <section>
            <h3>{{ t.whereToBuy }}</h3>
            <table class="yx-dialog__offers">
              <thead><tr><th>{{ t.shop }}</th><th>{{ t.variant }}</th><th>{{ t.price }}</th><th>{{ t.packSize }}</th><th>{{ t.availability }}</th><th /></tr></thead>
              <tbody>
                <tr v-for="(offer, index) in detail.offers" :key="index" :class="{ chosen: index === (state.choice[detail.id] ?? 0) }">
                  <td>{{ data.vendors[offer.vendor].name }}{{ offer.genuine ? '' : t.clone }}</td>
                  <td>{{ offer.variant ?? offer.code }}</td>
                  <td>{{ formatMoney(offer.price, locale) }}</td>
                  <td>{{ offer.pack }}</td>
                  <td>{{ offer.stock ?? (offer.status === 'observed' ? t.listed : offer.status) }}</td>
                  <td><a :href="offer.url" target="_blank" rel="noreferrer">{{ t.view }}</a></td>
                </tr>
              </tbody>
            </table>
          </section>
        </template>
      </ProductDialog>
    </template>
  </div>
</template>
