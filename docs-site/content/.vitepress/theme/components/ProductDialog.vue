<script setup lang="ts">
// Product page as a dialog (shop and print kit): image, buy box (slot), description, features,
// specifications, strength checks and tightening torques, where the part sits in the robot
// (assembly steps) and Learn wiki links.
// Closes on Esc, on the backdrop and on the close button; keeps keyboard focus inside while open and
// returns it to the element that opened it.
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { WIKI_TITLES, type PartStrength, type ProductInfo } from '../shop/products';
import { defineMessages, useLocale, useLocalePath } from '../i18n';

const useMessages = defineMessages({
  en: {
    close: 'Close', description: 'Description', specifications: 'Specifications', strength: 'Strength',
    strengthHint: 'Worst-case loads the robot can produce on itself (servo stall torque, hard landings); S = allowable / actual, at least 1.5 required. How it is calculated:',
    strengthLink: 'strength, torque and failure', check: 'Check', actual: 'Actual', allowable: 'Allowable', formula: 'Formula',
    torque: (thread: string, joint: string, engaged: number) => `${thread} into this part (${joint}, ${engaged} mm engaged): tighten to at most`,
    strips: (torque: number) => `(strips at about ${torque} N·m)`,
    inRobot: 'In the robot', fitted: 'Fitted in assembly', step: (step: number) => `step ${step}`, see3d: 'see it in 3D', learnMore: 'Learn more',
  },
  de: {
    close: 'Schließen', description: 'Beschreibung', specifications: 'Technische Daten', strength: 'Festigkeit',
    strengthHint: 'Ungünstigste Lasten, die der Roboter selbst erzeugen kann (Blockiermoment der Servos, harte Landungen); S = zulässig / tatsächlich, mindestens 1,5 erforderlich. Wie gerechnet wird:',
    strengthLink: 'Festigkeit, Drehmoment und Versagen', check: 'Nachweis', actual: 'Tatsächlich', allowable: 'Zulässig', formula: 'Formel',
    torque: (thread: string, joint: string, engaged: number) => `${thread} in dieses Teil (${joint}, ${engaged} mm Einschraubtiefe): höchstens anziehen mit`,
    strips: (torque: number) => `(überdreht bei etwa ${torque} N·m)`,
    inRobot: 'Im Roboter', fitted: 'Eingebaut in', step: (step: number) => `Schritt ${step}`, see3d: 'in 3D ansehen', learnMore: 'Mehr erfahren',
  },
});
const t = useMessages();
const locale = useLocale();
const localePath = useLocalePath();

const props = defineProps<{
  title: string;
  category: string;
  image: string | null;
  glyph: string;
  info: ProductInfo | undefined;
  steps: number[];
  specs?: Record<string, string>; // facts from the kit data (size, quantity, filament...), shown before the datasheet specs
  tint?: string; // image tint class suffix (print kit: 'graphite' renders the lime line art grey)
  strength?: PartStrength; // checks of strido_verify.strength that involve this part
}>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLElement | null>(null);
const closeButton = ref<HTMLButtonElement | null>(null);
let opener: HTMLElement | null = null;
const FOCUSABLE = 'a[href], button:not([disabled]), select, input, textarea, [tabindex]:not([tabindex="-1"])';

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close');
  if (event.key !== 'Tab' || !dialog.value) return;
  const focusable = [...dialog.value.querySelectorAll<HTMLElement>(FOCUSABLE)];
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const inside = dialog.value.contains(document.activeElement);
  if (event.shiftKey && (!inside || document.activeElement === first)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (!inside || document.activeElement === last)) {
    event.preventDefault();
    first.focus();
  }
}
onMounted(() => {
  opener = document.activeElement as HTMLElement | null;
  document.addEventListener('keydown', onKey);
  document.documentElement.classList.add('yx-dialog-open');
  closeButton.value?.focus();
});
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey);
  document.documentElement.classList.remove('yx-dialog-open');
  opener?.focus();
});

const allSpecs = () => ({ ...(props.specs ?? {}), ...(props.info?.specs ?? {}) });
</script>

<template>
  <div class="yx-dialog__backdrop" @click.self="emit('close')">
    <article ref="dialog" class="yx-dialog" role="dialog" aria-modal="true" :aria-label="title">
      <button ref="closeButton" type="button" class="yx-dialog__close" :aria-label="t.close" @click="emit('close')">✕</button>
      <div class="yx-dialog__top">
        <div class="yx-dialog__image" :class="tint ? `tint-${tint}` : ''">
          <img v-if="image" :src="image" :alt="title" />
          <span v-else class="yx-product__glyph">{{ glyph }}</span>
        </div>
        <div class="yx-dialog__buy">
          <span class="yx-product__category">{{ category }}</span>
          <h2>{{ title }}</h2>
          <p v-if="info?.summary" class="yx-dialog__summary">{{ info.summary }}</p>
          <slot name="buy" />
        </div>
      </div>
      <div class="yx-dialog__details">
        <section v-if="info?.description">
          <h3>{{ t.description }}</h3>
          <p>{{ info.description }}</p>
          <ul v-if="info.features?.length" class="yx-dialog__features">
            <li v-for="feature in info.features" :key="feature">{{ feature }}</li>
          </ul>
        </section>
        <section v-if="Object.keys(allSpecs()).length">
          <h3>{{ t.specifications }}</h3>
          <dl class="yx-dialog__specs">
            <template v-for="(value, name) in allSpecs()" :key="name"><dt>{{ name }}</dt><dd>{{ value }}</dd></template>
          </dl>
        </section>
        <slot name="details" />
        <section v-if="strength?.checks.length || strength?.torques.length">
          <h3>{{ t.strength }}</h3>
          <p class="yx-dialog__hint">{{ t.strengthHint }} <a :href="localePath('/docs/wiki/making/strength')">{{ t.strengthLink }}</a>.</p>
          <table v-if="strength?.checks.length" class="yx-dialog__strength">
            <thead><tr><th>{{ t.check }}</th><th>S</th><th>{{ t.actual }}</th><th>{{ t.allowable }}</th><th class="col-formula">{{ t.formula }}</th></tr></thead>
            <tbody>
              <tr v-for="item in strength.checks" :key="item.id" :class="`strength-${item.status}`" :title="item.note">
                <td>{{ item.what }}</td><td class="safety"><strong>{{ item.safety }}</strong></td>
                <td>{{ item.actual }} {{ item.unit }}</td><td>{{ item.allowable }} {{ item.unit }}</td>
                <td class="col-formula"><code>{{ item.formula }}</code></td>
              </tr>
            </tbody>
          </table>
          <p v-for="item in strength?.checks.filter((c) => c.note)" :key="`note-${item.id}`" class="yx-product__note">{{ item.note }}</p>
          <ul v-if="strength?.torques.length" class="yx-dialog__torques">
            <li v-for="item in strength.torques" :key="item.joint">
              {{ t.torque(item.thread, item.joint.replace(/_/g, ' '), item.engaged_mm) }} <strong>{{ item.recommended_torque_nm }} N·m</strong> {{ t.strips(item.strip_torque_nm) }}
            </li>
          </ul>
        </section>
        <section v-if="info?.role || steps.length">
          <h3>{{ t.inRobot }}</h3>
          <p v-if="info?.role">{{ info.role }}</p>
          <p v-if="steps.length" class="yx-dialog__steps">
            {{ t.fitted }}
            <template v-for="(step, index) in steps" :key="step">{{ index ? ', ' : ' ' }}<a :href="localePath(`/docs/assembly/#step-${step}`)">{{ t.step(step) }}</a></template>
            · <a :href="localePath('/docs/viewer')">{{ t.see3d }}</a>
          </p>
        </section>
        <section v-if="info?.learn?.length">
          <h3>{{ t.learnMore }}</h3>
          <div class="yx-dialog__learn">
            <a v-for="slug in info.learn" :key="slug" :href="localePath(`/docs/wiki/${slug}`)">{{ WIKI_TITLES[locale][slug] ?? slug }} →</a>
          </div>
        </section>
      </div>
    </article>
  </div>
</template>
