<script setup lang="ts">
// The open conversation: question bubbles with attachment thumbnails, rendered answers with their
// sources, the live status line with Stop while an answer streams, and failures with Retry. Keeps the
// newest text in view while the reader has not scrolled up.
import { nextTick, ref, watch } from 'vue';
import { useRouter } from 'vitepress';
import { INTERNAL_LINK_ATTR, internalRoute, renderMarkdown } from './markdown';
import { useAiMessages } from './messages';
import { attachmentUrl } from './useAssistantApi';
import type { ViewAttachment, ViewMessage } from './useConversations';

/** Distance from the bottom (px) within which new text keeps the view scrolled down. */
const FOLLOW_THRESHOLD = 48;
const COPIED_MS = 1500;

const props = defineProps<{
  messages: ViewMessage[];
  draft: string | null;
  statusText: string;
  streaming: boolean;
  loading: boolean;
  failureText: string;
  canRetry: boolean;
}>();
const emit = defineEmits<{ stop: []; retry: [] }>();
const t = useAiMessages();
const router = useRouter();
const scroller = ref<HTMLElement | null>(null);
let follow = true;
const rendered = new Map<string, { text: string; label: string; html: string }>();

function answerHtml(message: ViewMessage): string {
  const label = t.value.copyCode;
  const cached = rendered.get(message.id);
  if (cached && cached.text === message.text && cached.label === label) return cached.html;
  const html = renderMarkdown(message.text, label);
  rendered.set(message.id, { text: message.text, label, html });
  return html;
}

function thumbnail(file: ViewAttachment): string {
  return file.previewUrl ?? (file.id ? attachmentUrl(file.id) : '');
}

function onScroll() {
  const element = scroller.value;
  if (element) follow = element.scrollHeight - element.scrollTop - element.clientHeight < FOLLOW_THRESHOLD;
}

function onClick(event: MouseEvent) {
  const target = event.target as Element;
  const copy = target.closest<HTMLButtonElement>('.yx-ai-copy');
  if (copy) {
    void copyCode(copy);
    return;
  }
  const link = target.closest<HTMLAnchorElement>(`a[${INTERNAL_LINK_ATTR}]`);
  if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  void router.go(link.getAttribute(INTERNAL_LINK_ATTR) ?? '/');
}

async function copyCode(button: HTMLButtonElement) {
  const code = button.parentElement?.querySelector('code')?.textContent ?? '';
  try {
    await navigator.clipboard.writeText(code);
  } catch {
    return; // clipboard blocked: the code stays selectable
  }
  button.classList.add('is-copied');
  button.setAttribute('aria-label', t.value.copied);
  setTimeout(() => {
    button.classList.remove('is-copied');
    button.setAttribute('aria-label', t.value.copyCode);
  }, COPIED_MS);
}

// Another conversation: forget rendered answers and start at its newest message.
watch(
  () => props.messages,
  () => {
    rendered.clear();
    follow = true;
  },
);
watch(
  () => [props.messages.length, props.draft, props.statusText, props.failureText, props.loading],
  async () => {
    await nextTick();
    if (follow && scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight;
  },
  { flush: 'post', immediate: true },
);
</script>

<template>
  <div ref="scroller" class="yx-ai-messages" @scroll.passive="onScroll" @click="onClick">
    <p v-if="loading" class="yx-ai-messages__note">{{ t.loading }}</p>
    <div v-else-if="!messages.length && draft === null && !failureText" class="yx-ai-empty">
      <p class="yx-ai-empty__title">{{ t.emptyTitle }}</p>
      <p class="yx-ai-empty__hint">{{ t.emptyHint }}</p>
    </div>
    <article v-for="message in messages" :key="message.id" class="yx-ai-message" :class="`yx-ai-message--${message.role}`">
      <h3 class="yx-ai-sr">{{ message.role === 'user' ? t.you : t.assistant }}</h3>
      <template v-if="message.role === 'user'">
        <ul v-if="message.attachments.length" class="yx-ai-message__files">
          <li v-for="(file, index) in message.attachments" :key="file.id || index">
            <a v-if="file.mediaType.startsWith('image/') && thumbnail(file)" :href="file.id ? attachmentUrl(file.id) : thumbnail(file)" target="_blank" rel="noopener">
              <img :src="thumbnail(file)" :alt="file.name" loading="lazy" />
            </a>
            <span v-else class="yx-ai-file">{{ file.name }}</span>
          </li>
        </ul>
        <p v-if="message.text" class="yx-ai-message__text">{{ message.text }}</p>
      </template>
      <template v-else>
        <div class="yx-ai-markdown" v-html="answerHtml(message)" />
        <p v-if="message.status !== 'complete'" class="yx-ai-message__flag">{{ message.status === 'stopped' ? t.stopped : t.failed }}</p>
        <nav v-if="message.sources.length" class="yx-ai-sources" :aria-label="t.sources">
          <span class="yx-ai-sources__label">{{ t.sources }}</span>
          <ol>
            <li v-for="source in message.sources" :key="source.url">
              <a
                :href="source.url"
                :[INTERNAL_LINK_ATTR]="internalRoute(source.url) ?? undefined"
                :target="internalRoute(source.url) ? undefined : '_blank'"
                :rel="internalRoute(source.url) ? undefined : 'noopener noreferrer'"
                >{{ source.title }}</a
              >
            </li>
          </ol>
        </nav>
      </template>
    </article>
    <article v-if="draft" class="yx-ai-message yx-ai-message--assistant">
      <h3 class="yx-ai-sr">{{ t.assistant }}</h3>
      <div class="yx-ai-markdown" v-html="renderMarkdown(draft, t.copyCode)" />
    </article>
    <div class="yx-ai-status" role="status" aria-live="polite">
      <template v-if="streaming">
        <span class="yx-ai-status__dot" aria-hidden="true" />
        <span class="yx-ai-status__text">{{ statusText || t.thinking }}</span>
        <button type="button" class="yx-ai-button" @click="emit('stop')">{{ t.stop }}</button>
      </template>
    </div>
    <div v-if="failureText || canRetry" class="yx-ai-failure" :class="{ 'yx-ai-failure--error': failureText }">
      <p v-if="failureText" role="alert">{{ failureText }}</p>
      <button v-if="canRetry" type="button" class="yx-ai-button" @click="emit('retry')">{{ t.retry }}</button>
    </div>
  </div>
</template>
