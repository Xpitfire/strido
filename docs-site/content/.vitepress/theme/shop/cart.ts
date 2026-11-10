// Parts shop cart: the complete robot as a kit (all BOM lines of a shopping plan) plus single items.
// Pricing mirrors strido_publish.pricing / shopping: pieces are rounded up to whole packs, a shop's
// shipping is free from its threshold, its per-order fee always applies. Data: /bom/shop.json.
import { computed, reactive, ref, watch } from 'vue';
import { dataUrl, formatMoney, type Locale } from '../i18n';

export interface Offer { vendor: string; sku: string; variant: string | null; code: string; price: number; pack: number; status: string; stock: string | null; genuine: boolean; url: string }
export interface Line { id: string; name: string; category: string; qty: number; note: string | null; optional: boolean; cad: string[]; offers: Offer[] }
export interface Vendor { name: string; shipping: number; free_from: number | null; per_order_fee: number; note: string | null; region: string | null; url: string | null }
export interface Plan { key: string; letter: string; label: string; guide: string; total: number; shops: number; choice: Record<string, number> }
export interface ShopData { prices_observed: string; vendors: Record<string, Vendor>; lines: Line[]; plans: Plan[] }

interface Saved { plan: string; kits: number; choice: Record<string, number>; extras: Record<string, number>; owned: string[]; ordered?: string[] }

const STORAGE_KEY = 'yx-shop-cart';
export const KITS_MAX = 20;

export const data = ref<ShopData | null>(null);
export const loadError = ref('');
export const state = reactive({
  plan: 'lowest',
  kits: 0,
  choice: {} as Record<string, number>,
  extras: {} as Record<string, number>, // pieces bought in addition to the kits
  owned: [] as string[], // lines left out of the kit (already owned)
  ordered: [] as string[], // order keys (orderKey) already put into the shop's own cart (checkout checklist)
});

// Words inside offer option texts (plain strings: offerLabel is called outside a component setup).
const OFFER_WORDS = { en: { pieces: 'pcs', clone: 'clone' }, de: { pieces: 'Stk.', clone: 'Nachbau' } } satisfies Record<Locale, Record<string, string>>;

export function planOf(key: string): Plan | undefined {
  return data.value?.plans.find((plan) => plan.key === key);
}

export function offerOf(line: Line): Offer {
  return line.offers[state.choice[line.id] ?? 0];
}

/** Option text for an offer; when one shop lists the line twice, the variant (or order code) tells them apart. */
export function offerLabel(line: Line, offer: Offer, locale: Locale): string {
  const vendorName = data.value?.vendors[offer.vendor].name ?? offer.vendor;
  const twice = line.offers.filter((other) => other.vendor === offer.vendor).length > 1;
  const words = OFFER_WORDS[locale];
  return [
    `${vendorName} · ${formatMoney(offer.price, locale)}${offer.pack > 1 ? ` / ${offer.pack} ${words.pieces}` : ''}`,
    twice ? (offer.variant ?? offer.code) : '',
    offer.genuine ? '' : words.clone,
  ].filter(Boolean).join(' · ');
}

/** Checklist key of a cart row: a tick stays valid only for the same item, shop, order code and quantity. */
export function orderKey(row: CartRow): string {
  return `${row.line.id}|${row.offer.vendor}|${row.offer.code}|${row.packs}`;
}

export function setOrdered(key: string, ordered: boolean) {
  state.ordered = ordered ? [...new Set([...state.ordered, key])] : state.ordered.filter((item) => item !== key);
}

/** Product image of a BOM line: the render of its first CAD part, or none (a glyph is shown). */
export function imageOf(line: Line): string | null {
  return line.cad.length ? `/parts/${line.cad[0]}.png` : null;
}

export function usePlan(key: string) {
  const plan = planOf(key);
  if (!plan) return;
  state.plan = key;
  state.choice = { ...plan.choice };
}

export function addKit(count = 1) {
  state.kits = Math.min(KITS_MAX, state.kits + count);
}

export function setKits(count: number) {
  state.kits = Math.max(0, Math.min(KITS_MAX, Math.round(count) || 0));
}

export function addItem(lineId: string, pieces: number) {
  state.extras[lineId] = Math.max(0, (state.extras[lineId] ?? 0) + pieces);
  if (!state.extras[lineId]) delete state.extras[lineId];
}

export function setOwned(lineId: string, owned: boolean) {
  state.owned = owned ? [...new Set([...state.owned, lineId])] : state.owned.filter((id) => id !== lineId);
}

export function clearCart() {
  state.kits = 0;
  state.extras = {};
  state.owned = [];
  state.ordered = [];
}

/** One BOM line in a basket: pieces from the kits and extra pieces, bought in whole packs at the chosen offer. */
export interface CartRow { line: Line; offer: Offer; fromKits: number; extra: number; pieces: number; packs: number; cost: number }

/** A basket's part from one shop: its rows, subtotal and shipping. */
export interface ShopOrder { key: string; vendor: Vendor; rows: CartRow[]; subtotal: number; shipping: number; total: number; toFree: number }

/** Rows for `kits` robots plus extra pieces: pieces per line, packs rounded up, cost at the chosen offer. */
function rowsFor(kits: number, extras: Record<string, number>): CartRow[] {
  if (!data.value) return [];
  return data.value.lines
    .map((line) => {
      const fromKits = state.owned.includes(line.id) ? 0 : line.qty * kits;
      const extra = extras[line.id] ?? 0;
      const pieces = fromKits + extra;
      const offer = offerOf(line);
      const packs = Math.ceil(pieces / offer.pack);
      return { line, offer, fromKits, extra, pieces, packs, cost: packs * offer.price };
    })
    .filter((row) => row.pieces > 0);
}

/** Rows grouped per shop with subtotal and shipping (free from the threshold, per-order fee always). */
function shopsFor(rows: CartRow[]): ShopOrder[] {
  if (!data.value) return [];
  const byShop = new Map<string, CartRow[]>();
  for (const row of rows) {
    if (!byShop.has(row.offer.vendor)) byShop.set(row.offer.vendor, []);
    byShop.get(row.offer.vendor)!.push(row);
  }
  return [...byShop.entries()]
    .map(([key, shopRows]) => {
      const vendor = data.value!.vendors[key];
      const subtotal = shopRows.reduce((sum, row) => sum + row.cost, 0);
      const free = vendor.free_from !== null && subtotal >= vendor.free_from;
      const shipping = (free ? 0 : vendor.shipping) + (vendor.per_order_fee ?? 0);
      const toFree = vendor.free_from !== null && !free ? vendor.free_from - subtotal : 0;
      return { key, vendor, rows: shopRows, subtotal, shipping, total: subtotal + shipping, toFree };
    })
    .sort((a, b) => b.total - a.total);
}

/** Every line in the cart: pieces from the kits (unless owned) plus extra pieces. */
export const cartRows = computed(() => rowsFor(state.kits, state.extras));
export const shops = computed(() => shopsFor(cartRows.value));

/** One robot at the chosen shops (owned lines excluded): parts, shipping and total as if ordered alone. */
export const kitSummary = computed(() => {
  const kitShops = shopsFor(rowsFor(1, {}));
  const parts = kitShops.reduce((sum, shop) => sum + shop.subtotal, 0);
  const shipping = kitShops.reduce((sum, shop) => sum + shop.shipping, 0);
  return { parts, shipping, total: parts + shipping, shops: kitShops.length };
});

export const itemsTotal = computed(() => shops.value.reduce((sum, shop) => sum + shop.subtotal, 0));
export const shippingTotal = computed(() => shops.value.reduce((sum, shop) => sum + shop.shipping, 0));
export const grandTotal = computed(() => itemsTotal.value + shippingTotal.value);
export const cartCount = computed(() => state.kits + Object.values(state.extras).reduce((sum, n) => sum + n, 0));

export function orderList(shop: ShopOrder): string {
  const rows = shop.rows.map(
    (row) => `${row.packs}\t${row.offer.code}\t${row.line.name}${row.offer.pack > 1 ? ` (pack of ${row.offer.pack})` : ''}\t${row.offer.url}`,
  );
  return ['Order quantity\tOrder code\tItem\tLink', ...rows].join('\n') + '\n';
}

function csvCell(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function cartCsv(): string {
  const header = ['shop', 'order quantity', 'pack size', 'order code', 'item', 'price per pack (EUR)', 'cost (EUR)', 'link'];
  const rows = shops.value.flatMap((shop) =>
    shop.rows.map((row) => [shop.vendor.name, row.packs, row.offer.pack, row.offer.code, row.line.name, row.offer.price.toFixed(2), row.cost.toFixed(2), row.offer.url]),
  );
  return [header, ...rows].map((cells) => cells.map(csvCell).join(',')).join('\n') + '\n';
}

export function download(name: string, blob: Blob) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

let loading: Promise<void> | null = null;
let loadedLocale: Locale | null = null;
let restored = false;

/**
 * Loads the shop data of the site language (again when the language changes; the cart keeps its
 * line ids) and restores the saved cart once (browser only).
 */
export function loadShop(locale: Locale): Promise<void> {
  if (loading && loadedLocale === locale) return loading;
  loadedLocale = locale;
  loading = (async () => {
    try {
      const response = await fetch(dataUrl('/bom/shop.json', locale));
      if (!response.ok) throw new Error(`shop data: HTTP ${response.status}`);
      const shop = (await response.json()) as ShopData;
      if (loadedLocale !== locale) return; // the language changed while this answer was on its way
      data.value = shop;
      loadError.value = '';
      if (restored) return;
      restored = true;
      usePlan('lowest');
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) restore(JSON.parse(saved) as Saved);
      watch(state, () => localStorage.setItem(STORAGE_KEY, JSON.stringify(state)), { deep: true });
    } catch (cause) {
      loadError.value = (cause as Error).message;
    }
  })();
  return loading;
}

function restore(saved: Saved) {
  const lines = new Map(data.value!.lines.map((line) => [line.id, line]));
  if (planOf(saved.plan)) usePlan(saved.plan);
  for (const [id, index] of Object.entries(saved.choice ?? {})) {
    if ((lines.get(id)?.offers.length ?? 0) > index) state.choice[id] = index;
  }
  state.kits = Math.max(0, Math.min(KITS_MAX, saved.kits ?? 0));
  state.extras = Object.fromEntries(Object.entries(saved.extras ?? {}).filter(([id, n]) => lines.has(id) && n > 0));
  state.owned = (saved.owned ?? []).filter((id) => lines.has(id));
  state.ordered = (saved.ordered ?? []).filter((key) => lines.has(key.split('|')[0]));
}
