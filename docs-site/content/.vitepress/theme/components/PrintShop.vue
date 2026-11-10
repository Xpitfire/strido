<script setup lang="ts">
// Print kit builder: every printed part with its render, quantity per robot, colour, supports,
// filament and print time (from the printability gate); pick parts and quantities and download a
// ready-to-print ZIP (STLs named with their quantity, the slicer profile, a parts sheet, and for
// complete robots the ready 3MF plates). Built in the browser from the files the site serves.
import { computed, onMounted, reactive, ref } from 'vue';
import { buildZip, text, type ZipEntry } from '../shop/zip';
import { download } from '../shop/cart';
import { loadProducts, productInfo, strengthOf } from '../shop/products';
import ProductDialog from './ProductDialog.vue';
import { dataUrl, defineMessages, useLocale } from '../i18n';

const useMessages = defineMessages({
  en: {
    perRobot: 'Per robot', size: 'Size', asPrinted: '(as printed)', colour: 'Colour', filament: 'Filament', printTime: 'Print time',
    supports: 'Supports', supportsYes: 'yes (snug, from the bed)', none: 'none', brim: 'Brim', file: 'File',
    graphite: 'Graphite (frame, legs, mounts)', lime: 'Lime (shells and shoulders)', collecting: 'Collecting files…', packing: 'Packing…',
    failed: (message: string) => `Failed: ${message}`, loadError: (error: string) => `Could not load the print data (${error}).`, loading: 'Loading the print kit…',
    pieces: 'Pieces', graphiteShort: 'Graphite', limeShort: 'Lime', printing: 'Printing', robots: 'Robots',
    completeRobots: (robots: number) => (robots > 1 ? 'Complete robots' : 'Complete robot'), clear: 'Clear',
    download: (parts: number, plates: boolean) => `Download print package (${parts} parts${plates ? ' + plates' : ''})`,
    hint: (slicer: string) => `Every part is oriented for printing and was sliced with the included profile (${slicer}) without errors or stability warnings. The package holds the STLs named with their quantity, the slicer profile and a parts sheet; for complete robots also the ready 3MF build plates.`,
    details: (title: string) => `Details: ${title}`, colourName: (key: string) => key, perRobotSize: (qty: number, size: string) => `${qty} per robot · ${size}`,
    each: 'each', supportsTag: ' · supports', brimTag: ' · brim', fewer: (title: string) => `fewer ${title}`, more: (title: string) => `more ${title}`,
    printed: 'printed', inPackage: 'In your print package', downloadStl: 'Download STL', printNote: (note: string) => `Print note: ${note}`,
  },
  de: {
    perRobot: 'Pro Roboter', size: 'Größe', asPrinted: '(wie gedruckt)', colour: 'Farbe', filament: 'Filament', printTime: 'Druckzeit',
    supports: 'Stützen', supportsYes: 'ja (eng anliegend, vom Druckbett)', none: 'keine', brim: 'Brim', file: 'Datei',
    graphite: 'Graphit (Rahmen, Beine, Halterungen)', lime: 'Limette (Schalen und Schultern)', collecting: 'Dateien werden gesammelt…', packing: 'Wird gepackt…',
    failed: (message: string) => `Fehlgeschlagen: ${message}`, loadError: (error: string) => `Die Druckdaten konnten nicht geladen werden (${error}).`, loading: 'Druckpaket wird geladen…',
    pieces: 'Teile', graphiteShort: 'Graphit', limeShort: 'Limette', printing: 'Druckzeit', robots: 'Roboter',
    completeRobots: (robots: number) => (robots > 1 ? 'Komplette Roboter' : 'Kompletter Roboter'), clear: 'Leeren',
    download: (parts: number, plates: boolean) => `Druckpaket herunterladen (${parts} Teile${plates ? ' + Druckplatten' : ''})`,
    hint: (slicer: string) => `Jedes Teil ist druckfertig ausgerichtet und wurde mit dem beiliegenden Profil (${slicer}) ohne Fehler oder Stabilitätswarnungen gesliced. Das Paket enthält die STLs mit ihrer Stückzahl im Namen, das Slicer-Profil und eine Teileliste; für komplette Roboter zusätzlich die fertigen 3MF-Druckplatten.`,
    details: (title: string) => `Details: ${title}`, colourName: (key: string) => (key === 'lime' ? 'Limette' : 'Graphit'), perRobotSize: (qty: number, size: string) => `${qty} pro Roboter · ${size}`,
    each: 'je Stück', supportsTag: ' · Stützen', brimTag: ' · Brim', fewer: (title: string) => `weniger ${title}`, more: (title: string) => `mehr ${title}`,
    printed: 'gedruckt', inPackage: 'In Ihrem Druckpaket', downloadStl: 'STL herunterladen', printNote: (note: string) => `Druckhinweis: ${note}`,
  },
});
const t = useMessages();
const locale = useLocale();

interface CatalogPart { id: string; kind: string; title: string; qty: number; steps: number[]; image: string | null; bbox_mm: number[]; file: string; colour: string; supports: boolean; note: string }
interface Printability { part: string; filament_g: number; print_time_s: number; brim: boolean; status: string }
interface PrintData { parts: Printability[]; plates: { plate: string }[]; slicer: string }

const ROBOTS_MAX = 20;
const parts = ref<CatalogPart[]>([]);
const stats = ref<Record<string, Printability>>({});
const plates = ref<string[]>([]);
const slicer = ref('');
const error = ref('');
const robots = ref(1);
const qty = reactive<Record<string, number>>({});
const busy = ref(''); // progress text while the package is built
const failure = ref(''); // why the last package could not be built
const detail = ref<CatalogPart | null>(null);
const DETAIL_HASH = '#part=';

/** Opens the part page; the URL hash makes it shareable (#part=<id>). */
function openDetail(part: CatalogPart | null) {
  detail.value = part;
  history.replaceState(history.state, '', part ? `${DETAIL_HASH}${encodeURIComponent(part.id)}` : location.pathname + location.search);
}

function partSpecs(part: CatalogPart): Record<string, string> {
  const s = stats.value[part.id];
  return {
    [t.value.perRobot]: String(part.qty),
    [t.value.size]: `${sizeOf(part)} ${t.value.asPrinted}`,
    [t.value.colour]: t.value.colourName(colourKey(part)),
    [t.value.filament]: s ? `${s.filament_g.toFixed(1)} g PETG` : '–',
    [t.value.printTime]: s ? hours(s.print_time_s) : '–',
    [t.value.supports]: part.supports ? t.value.supportsYes : t.value.none,
    [t.value.brim]: s?.brim ? '5 mm' : t.value.none,
    [t.value.file]: `stl/${fileName(part)}`,
  };
}

const hours = (seconds: number) => `${Math.floor(seconds / 3600)} h ${String(Math.round((seconds % 3600) / 60)).padStart(2, '0')} min`;
const fileName = (part: CatalogPart) => part.file.split('/').pop()!;
const colourKey = (part: CatalogPart) => (part.colour.startsWith('secondary') ? 'lime' : 'graphite');
// Bounding box to 0.1 mm without trailing zeros, e.g. "26 × 26 × 4.5 mm".
const sizeOf = (part: CatalogPart) => `${part.bbox_mm.map((v) => Number(v.toFixed(1))).join(' × ')} mm`;

function resetToRobots() {
  for (const part of parts.value) qty[part.id] = part.qty * robots.value;
}

onMounted(async () => {
  try {
    const [catalog, printability] = await Promise.all([
      fetch(dataUrl('/catalog/parts.json', locale.value)).then((r) => r.json()),
      fetch('/data/printability.json').then((r) => r.json()) as Promise<PrintData>,
    ]);
    parts.value = (catalog.parts as CatalogPart[]).filter((part) => part.kind === 'printed');
    stats.value = Object.fromEntries(printability.parts.map((p) => [p.part, p]));
    plates.value = printability.plates.map((p) => p.plate);
    slicer.value = printability.slicer.split(' ')[0]; // "PrusaSlicer-2.9.6 based on Slic3r ..." -> "PrusaSlicer-2.9.6"
    resetToRobots();
  } catch (cause) {
    error.value = (cause as Error).message;
  }
  loadProducts(locale.value);
  const id = location.hash.startsWith(DETAIL_HASH) ? decodeURIComponent(location.hash.slice(DETAIL_HASH.length)) : '';
  detail.value = parts.value.find((part) => part.id === id) ?? null;
});

const selected = computed(() => parts.value.filter((part) => (qty[part.id] ?? 0) > 0));
const groups = computed(() => [
  { key: 'graphite', title: t.value.graphite, parts: parts.value.filter((p) => colourKey(p) === 'graphite') },
  { key: 'lime', title: t.value.lime, parts: parts.value.filter((p) => colourKey(p) === 'lime') },
]);
const totals = computed(() => {
  const result = { pieces: 0, seconds: 0, graphite: 0, lime: 0 };
  for (const part of selected.value) {
    const n = qty[part.id];
    const s = stats.value[part.id];
    result.pieces += n;
    result.seconds += (s?.print_time_s ?? 0) * n;
    result[colourKey(part)] += (s?.filament_g ?? 0) * n;
  }
  return result;
});
const completeRobots = computed(() => parts.value.length > 0 && parts.value.every((part) => qty[part.id] === part.qty * robots.value));

function step(part: CatalogPart, delta: number) {
  qty[part.id] = Math.max(0, (qty[part.id] ?? 0) + delta);
}

function setAll(on: boolean) {
  if (on) resetToRobots();
  else for (const part of parts.value) qty[part.id] = 0;
}

function readme(): string {
  const columns = (qtyText: string, file: string, colour: string, grams: string, time: string, notes: string) =>
    `${qtyText.padStart(3)}  ${file.padEnd(44)} ${colour.padEnd(8)} ${grams.padStart(8)} ${time.padStart(11)}  ${notes}`.trimEnd();
  const rows = selected.value.map((part) => {
    const s = stats.value[part.id];
    const notes = [part.supports ? 'supports' : '', s?.brim ? 'brim 5 mm' : '', part.note].filter(Boolean).join('; ');
    const file = `stl/${qty[part.id]}x_${fileName(part)}`;
    return columns(String(qty[part.id]), file, colourKey(part), `${(s?.filament_g ?? 0).toFixed(1)} g`, hours(s?.print_time_s ?? 0), notes);
  });
  return [
    'Strido print package',
    '======================',
    '',
    `${totals.value.pieces} pieces: graphite ${Math.round(totals.value.graphite)} g, lime ${Math.round(totals.value.lime)} g, about ${hours(totals.value.seconds)} of printing (per-piece slicer estimates).`,
    '',
    '1. Import prusaslicer.ini into PrusaSlicer (File > Import > Import Config). It is the profile every part was',
    `   verified with (${slicer.value}): 0.4 mm nozzle, 0.2 mm layers, 3 perimeters, 5 top/bottom layers,`,
    '   30 % gyroid, PETG. Other slicers: enter the same values.',
    completeRobots.value
      ? `2. Easiest: print every plate in plates/ ${robots.value > 1 ? `${robots.value} times` : 'once'} (graphite plates in graphite, lime plates in lime).\n   Or print single parts from stl/ in the quantity in the file name.`
      : '2. Print each file in stl/ as many times as its name says (e.g. 4x_femur.stl = 4 pieces).',
    '3. Supports and brims as listed below; the STLs are already oriented for printing.',
    '',
    columns('qty', 'file', 'colour', 'filament', 'time each', 'notes'),
    ...rows,
    '',
  ].join('\n');
}

async function fetchBytes(url: string): Promise<Uint8Array> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return new Uint8Array(await response.arrayBuffer());
}

async function downloadPackage() {
  busy.value = t.value.collecting;
  failure.value = '';
  try {
    const root = 'strido-print-package';
    const entries: ZipEntry[] = [
      { name: `${root}/README.txt`, data: text(readme()) },
      { name: `${root}/prusaslicer.ini`, data: await fetchBytes('/print/prusaslicer.ini') },
    ];
    for (const part of selected.value) {
      entries.push({ name: `${root}/stl/${qty[part.id]}x_${fileName(part)}`, data: await fetchBytes(`/print/stl/${fileName(part)}`) });
    }
    if (completeRobots.value) {
      for (const plate of plates.value) entries.push({ name: `${root}/plates/${plate}`, data: await fetchBytes(`/print/plates/${plate}`) });
    }
    busy.value = t.value.packing;
    const name = completeRobots.value ? `strido-print-package-${robots.value}-robot${robots.value > 1 ? 's' : ''}.zip` : 'strido-print-package-selection.zip';
    download(name, buildZip(entries));
  } catch (cause) {
    failure.value = t.value.failed((cause as Error).message);
  } finally {
    busy.value = '';
  }
}
</script>

<template>
  <div class="yx-store">
    <p v-if="error" class="yx-store__error">{{ t.loadError(error) }}</p>
    <p v-else-if="!parts.length">{{ t.loading }}</p>
    <template v-else>
      <section class="yx-printbar">
        <div><span>{{ t.pieces }}</span><strong>{{ totals.pieces }}</strong></div>
        <div><span>{{ t.graphiteShort }}</span><strong>{{ Math.round(totals.graphite) }} g</strong></div>
        <div><span>{{ t.limeShort }}</span><strong>{{ Math.round(totals.lime) }} g</strong></div>
        <div><span>{{ t.printing }}</span><strong>{{ hours(totals.seconds) }}</strong></div>
        <label class="yx-printbar__robots">{{ t.robots }}
          <input v-model.number="robots" type="number" min="1" :max="ROBOTS_MAX" @change="resetToRobots" />
        </label>
        <div class="yx-printbar__actions">
          <button type="button" class="yx-btn" @click="setAll(true)">{{ t.completeRobots(robots) }}</button>
          <button type="button" class="yx-btn" @click="setAll(false)">{{ t.clear }}</button>
          <button type="button" class="yx-btn yx-btn--primary" :disabled="!selected.length || !!busy" @click="downloadPackage">
            {{ busy || t.download(selected.length, completeRobots) }}
          </button>
        </div>
        <p v-if="failure" class="yx-store__error">{{ failure }}</p>
      </section>
      <p class="yx-store__hint">{{ t.hint(slicer) }}</p>

      <section v-for="group in groups" :key="group.key">
        <h2 :id="`print-${group.key}`">{{ group.title }}</h2>
        <div class="yx-store__grid">
          <article v-for="part in group.parts" :key="part.id" class="yx-product" :class="{ owned: !qty[part.id] }">
            <button type="button" class="yx-product__image" :class="`tint-${colourKey(part)}`" :aria-label="t.details(part.title)" @click="openDetail(part)">
              <img v-if="part.image" :src="part.image" :alt="part.title" loading="lazy" />
            </button>
            <div class="yx-product__body">
              <span class="yx-product__category" :class="`colour-${colourKey(part)}`">{{ t.colourName(colourKey(part)) }}</span>
              <h3><button type="button" class="yx-product__title" @click="openDetail(part)">{{ part.title }}</button></h3>
              <p v-if="productInfo?.printed[part.id]" class="yx-product__summary">{{ productInfo.printed[part.id].summary }}</p>
              <p class="yx-product__kit">{{ t.perRobotSize(part.qty, sizeOf(part)) }}</p>
              <p class="yx-product__stock">
                {{ stats[part.id]?.filament_g.toFixed(1) }} g · {{ hours(stats[part.id]?.print_time_s ?? 0) }} {{ t.each }}{{ part.supports ? t.supportsTag : '' }}{{ stats[part.id]?.brim ? t.brimTag : '' }}
              </p>
              <div class="yx-product__buy">
                <div class="yx-stepper">
                  <button type="button" :aria-label="t.fewer(part.title)" @click="step(part, -1)">−</button><span>{{ qty[part.id] }}</span>
                  <button type="button" :aria-label="t.more(part.title)" @click="step(part, 1)">+</button>
                </div>
                <a class="yx-product__file" :href="`/print/stl/${fileName(part)}`" download>STL</a>
              </div>
            </div>
          </article>
        </div>
      </section>

      <ProductDialog
        v-if="detail"
        :title="detail.title"
        :category="`${t.printed} · ${t.colourName(colourKey(detail))}`"
        :image="detail.image"
        glyph=""
        :info="productInfo?.printed[detail.id]"
        :steps="detail.steps ?? []"
        :specs="partSpecs(detail)"
        :tint="colourKey(detail)"
        :strength="strengthOf(detail.id)"
        @close="openDetail(null)"
      >
        <template #buy>
          <p class="yx-product__kit">{{ t.inPackage }}</p>
          <div class="yx-dialog__actions">
            <div class="yx-stepper">
              <button type="button" :aria-label="t.fewer(detail.title)" @click="step(detail, -1)">−</button><span>{{ qty[detail.id] }}</span>
              <button type="button" :aria-label="t.more(detail.title)" @click="step(detail, 1)">+</button>
            </div>
            <a class="yx-btn" :href="`/print/stl/${fileName(detail)}`" download>{{ t.downloadStl }}</a>
          </div>
          <p v-if="detail.note" class="yx-product__note">{{ t.printNote(detail.note) }}</p>
        </template>
      </ProductDialog>
    </template>
  </div>
</template>
