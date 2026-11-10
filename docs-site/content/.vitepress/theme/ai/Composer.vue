<script setup lang="ts">
// Question input: growing textarea (Enter sends, Shift+Enter breaks the line, IME-safe), file picker,
// and removable attachment chips with thumbnails. Pasting and dropping are handled by the bar.
import { computed, nextTick, ref, watch } from 'vue';
import { ACCEPT, type PendingAttachment } from './attachments';
import { useAiMessages } from './messages';

/** Tallest the textarea grows before it scrolls, px. */
const MAX_TEXTAREA_HEIGHT = 200;
/** Show the remaining characters once this share of the limit is used. */
const COUNTER_FROM = 0.9;

const props = defineProps<{
  attachments: PendingAttachment[];
  maxChars: number;
  busy: boolean;
  preparing: boolean;
  notice: string;
}>();
const text = defineModel<string>({ required: true });
const emit = defineEmits<{ submit: []; attach: [files: File[]]; remove: [key: number] }>();
const t = useAiMessages();
const textarea = ref<HTMLTextAreaElement | null>(null);
const picker = ref<HTMLInputElement | null>(null);

const canSend = computed(() => !props.busy && !props.preparing && (text.value.trim() !== '' || props.attachments.length > 0));
const remaining = computed(() => props.maxChars - text.value.length);

function resize() {
  const element = textarea.value;
  if (!element) return;
  element.style.height = 'auto';
  element.style.height = `${Math.min(element.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
}

function onKeydown(event: KeyboardEvent) {
  // keyCode 229: a key consumed by an input method editor (Safari reports isComposing late).
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) return;
  event.preventDefault();
  if (canSend.value) emit('submit');
}

function onPicked() {
  const files = Array.from(picker.value?.files ?? []);
  if (picker.value) picker.value.value = '';
  if (files.length) emit('attach', files);
}

function sizeLabel(bytes: number): string {
  return bytes < 1048576 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
}

watch(text, () => nextTick(resize));
defineExpose({ focus: () => textarea.value?.focus() });
</script>

<template>
  <form class="yx-ai-composer" @submit.prevent="canSend && emit('submit')">
    <ul v-if="attachments.length || preparing" class="yx-ai-chips">
      <li v-for="file in attachments" :key="file.key" class="yx-ai-chip">
        <img v-if="file.previewUrl" :src="file.previewUrl" alt="" class="yx-ai-chip__thumb" />
        <svg v-else class="yx-ai-chip__thumb" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 2h8l6 6v14H6V2Zm7 1.5V9h5.5L13 3.5ZM8 13h8v1.5H8V13Zm0 3h8v1.5H8V16Z" /></svg>
        <span class="yx-ai-chip__name" :title="file.name">{{ file.name }}</span>
        <span class="yx-ai-chip__size">{{ sizeLabel(file.size) }}</span>
        <button type="button" class="yx-ai-chip__remove" :aria-label="t.remove(file.name)" :title="t.remove(file.name)" @click="emit('remove', file.key)">×</button>
      </li>
      <li v-if="preparing" class="yx-ai-chip yx-ai-chip--busy">{{ t.preparing }}</li>
    </ul>
    <p v-if="notice" class="yx-ai-composer__notice" role="alert">{{ notice }}</p>
    <div class="yx-ai-composer__row">
      <button type="button" class="yx-ai-icon" :aria-label="t.attach" :title="t.attach" @click="picker?.click()">
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M16.5 6.5v10a4.5 4.5 0 0 1-9 0V5a3 3 0 0 1 6 0v10.5a1.5 1.5 0 0 1-3 0V6.5H9v9a3 3 0 0 0 6 0V5a4.5 4.5 0 0 0-9 0v11.5a6 6 0 0 0 12 0v-10h-1.5Z" /></svg>
      </button>
      <input ref="picker" type="file" multiple :accept="ACCEPT" hidden @change="onPicked" />
      <textarea
        ref="textarea"
        v-model="text"
        class="yx-ai-composer__input"
        rows="1"
        :placeholder="t.placeholder"
        :aria-label="t.placeholder"
        :maxlength="maxChars"
        enterkeyhint="send"
        @keydown="onKeydown"
      />
      <button type="submit" class="yx-ai-send" :aria-label="t.send" :title="t.send" :disabled="!canSend">
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M3 20.5 21 12 3 3.5v6.6L15 12 3 13.9z" /></svg>
      </button>
    </div>
    <p class="yx-ai-composer__hint">
      <span>{{ t.composerHint }}</span>
      <span v-if="text.length >= maxChars * COUNTER_FROM" aria-live="polite">{{ t.charsLeft(remaining) }}</span>
    </p>
  </form>
</template>
