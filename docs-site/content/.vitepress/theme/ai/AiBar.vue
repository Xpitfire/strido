<script setup lang="ts">
// The site's AI assistant bar, mounted once for every page (client-only). States: a pill at the bottom
// (collapsed), a panel in the middle of the screen (floating) or a sidebar on the right (pinned; the page
// makes room via a body class). `/` opens it (Cmd/Ctrl+K stays the search), Esc steps back, Alt+N starts a new
// conversation; files can be attached by picking, pasting or dropping. The pin choice and the last open
// conversation are remembered in localStorage.
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useData, useRoute } from 'vitepress';
import { useLocale } from '../i18n';
import { prepareAttachment, type PendingAttachment } from './attachments';
import Composer from './Composer.vue';
import ConversationHeader from './ConversationHeader.vue';
import ConversationList from './ConversationList.vue';
import { describeError, useAiMessages } from './messages';
import { AssistantError, assistantApi, type AnswerContext, type Me } from './useAssistantApi';
import { useConversations } from './useConversations';
import './ai.css';

// Markdown, sanitizer and KaTeX load with the first opened panel, not with every page.
const MessageList = defineAsyncComponent(() => import('./MessageList.vue'));

type Mode = 'collapsed' | 'floating' | 'pinned';

/** 'pinned': pinned and open; 'pinned-closed': pinned preference while collapsed; absent: floating. */
const LAYOUT_KEY = 'yx-ai-layout';
const CONVERSATION_KEY = 'yx-ai-conversation';
/** Pasted text longer than this becomes a text attachment instead of composer text. */
const PASTE_AS_FILE_CHARS = 2000;
const PHONE_QUERY = '(max-width: 639px)';
const PINNED_BODY_CLASS = 'yx-ai-pinned';
const EDITABLE_TAGS = ['INPUT', 'TEXTAREA', 'SELECT'];

const t = useAiMessages();
const locale = useLocale();
const route = useRoute();
const { page } = useData();
const chat = useConversations();

const mounted = ref(false);
const mode = ref<Mode>('collapsed');
const pinPreferred = ref(false);
const me = ref<Me | null>(null);
const meError = ref<unknown>(null);
const listOpen = ref(false);
const draftText = ref('');
const pending = ref<PendingAttachment[]>([]);
const preparing = ref(0);
const notice = ref('');
const dragDepth = ref(0);
const pill = ref<HTMLButtonElement | null>(null);
const panel = ref<HTMLElement | null>(null);
const composer = ref<InstanceType<typeof Composer> | null>(null);
let pasteCount = 0;
let historyLoaded = false;

const locked = computed(() => me.value?.enabled === false || meError.value !== null);
const lockReason = computed(() => {
  if (me.value?.enabled === false) return me.value.reason || t.value.errorUnavailable;
  if (meError.value instanceof AssistantError && meError.value.status === 401) return t.value.errorSignedOut;
  return meError.value ? t.value.unreachable : '';
});
const title = computed(() => chat.current.value?.title || t.value.newConversation);
const failureText = computed(() => (chat.failure.value ? describeError(chat.failure.value, t.value) : ''));

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // storage blocked: nothing is remembered
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // storage blocked: the choice holds for this page view only
  }
}

function isEditable(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.isContentEditable || EDITABLE_TAGS.includes(target.tagName));
}

async function loadMe() {
  try {
    me.value = await assistantApi.me();
    meError.value = null;
  } catch (error) {
    meError.value = error;
  }
}

async function loadHistory() {
  historyLoaded = true;
  await chat.refresh();
  if (chat.currentId.value || chat.streaming.value || chat.messages.value.length) return;
  const stored = readStorage(CONVERSATION_KEY);
  const target = chat.conversations.value.find((conversation) => conversation.id === stored) ?? chat.conversations.value[0];
  if (target) await chat.select(target.id);
}

function setMode(next: Mode) {
  mode.value = next;
  writeStorage(LAYOUT_KEY, pinPreferred.value ? (next === 'pinned' ? 'pinned' : 'pinned-closed') : null);
}

async function focusComposer() {
  await nextTick();
  composer.value?.focus();
}

async function open() {
  // The panel needs the user's limits from /me before anything can be attached or sent.
  if (locked.value || !me.value) {
    await loadMe();
    if (locked.value) return;
  }
  if (mode.value === 'collapsed') setMode(pinPreferred.value ? 'pinned' : 'floating');
  void focusComposer();
  if (!historyLoaded) await loadHistory();
}

async function collapse() {
  listOpen.value = false;
  setMode('collapsed');
  await nextTick();
  pill.value?.focus();
}

function togglePin() {
  pinPreferred.value = !pinPreferred.value;
  setMode(pinPreferred.value ? 'pinned' : 'floating');
}

function toggleList() {
  listOpen.value = !listOpen.value;
  if (listOpen.value) void chat.refresh();
}

function newConversation() {
  if (chat.streaming.value) return;
  chat.startNew();
  listOpen.value = false;
  void focusComposer();
}

function selectConversation(id: string) {
  listOpen.value = false;
  void chat.select(id);
  void focusComposer();
}

async function addFiles(files: File[]) {
  const limits = me.value?.limits;
  if (!limits) return;
  notice.value = '';
  for (const file of files) {
    if (pending.value.length + preparing.value >= limits.maxAttachments) {
      notice.value = t.value.tooManyFiles(limits.maxAttachments);
      return;
    }
    preparing.value++;
    try {
      pending.value.push(await prepareAttachment(file, limits));
    } catch (error) {
      notice.value = describeError(error, t.value);
    } finally {
      preparing.value--;
    }
  }
}

function answerContext(): AnswerContext {
  return { locale: locale.value, page: { path: route.path, title: page.value.title } };
}

function submit() {
  const text = draftText.value.trim();
  if ((!text && !pending.value.length) || chat.streaming.value || chat.messagesLoading.value || preparing.value) return;
  const attachments = pending.value;
  draftText.value = '';
  pending.value = [];
  notice.value = '';
  listOpen.value = false;
  void chat.send({ text, attachments, context: answerContext() });
}

// Capture phase: `/` opens the bar before the search box (which also listens to it) sees it; Cmd/Ctrl+K
// stays the search shortcut.
function onShortcut(event: KeyboardEvent) {
  if (locked.value || document.querySelector('.VPLocalSearchBox')) return;
  if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey || isEditable(event.target)) return;
  event.preventDefault();
  event.stopPropagation();
  void open();
}

function onKeydown(event: KeyboardEvent) {
  if (mode.value === 'collapsed' || event.defaultPrevented || event.isComposing) return;
  const inPanel = panel.value?.contains(document.activeElement) ?? false;
  if (event.key === 'Escape' && (inPanel || (mode.value === 'floating' && document.activeElement === document.body))) {
    event.preventDefault();
    if (listOpen.value) listOpen.value = false;
    else void collapse();
  } else if (inPanel && event.altKey && event.key.toLowerCase() === 'n' && !event.metaKey && !event.ctrlKey) {
    // event.key, not event.code: on macOS Option+N types a character (˜, ñ) and is left alone.
    event.preventDefault();
    newConversation();
  }
}

function onPaste(event: ClipboardEvent) {
  const clipboard = event.clipboardData;
  if (mode.value === 'collapsed' || !clipboard) return;
  const inPanel = panel.value?.contains(event.target as Node) ?? false;
  if (isEditable(event.target) && !inPanel) return;
  const files = Array.from(clipboard.files);
  const text = clipboard.getData('text/plain');
  if (files.length) {
    event.preventDefault();
    void addFiles(files.map((file) => (file.type.startsWith('image/') ? new File([file], `pasted-${++pasteCount}.png`, { type: file.type }) : file)));
  } else if (text.length > PASTE_AS_FILE_CHARS) {
    event.preventDefault();
    void addFiles([new File([text], `pasted-${++pasteCount}.txt`, { type: 'text/plain' })]);
  } else if (text && !inPanel) {
    event.preventDefault();
    draftText.value += text;
    void focusComposer();
  }
}

const carriesFiles = (event: DragEvent) => event.dataTransfer?.types.includes('Files') ?? false;

function onDragEnter(event: DragEvent) {
  if (!carriesFiles(event) || locked.value) return;
  if (mode.value === 'collapsed') {
    if (!pill.value?.contains(event.target as Node)) return;
    void open();
  }
  event.preventDefault();
  dragDepth.value++;
}

function onDragOver(event: DragEvent) {
  if (!carriesFiles(event) || (mode.value === 'collapsed' && dragDepth.value === 0)) return;
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
}

function onDragLeave(event: DragEvent) {
  // Leaving the window has no related target; the pill's own leave event can be lost when it unmounts.
  if (event.relatedTarget === null) dragDepth.value = 0;
  else if (dragDepth.value > 0) dragDepth.value--;
}

function onDrop(event: DragEvent) {
  if (!carriesFiles(event) || (mode.value === 'collapsed' && dragDepth.value === 0)) return;
  event.preventDefault();
  dragDepth.value = 0;
  void addFiles(Array.from(event.dataTransfer?.files ?? []));
  void focusComposer();
}

const windowListeners = [
  ['keydown', onShortcut, true],
  ['keydown', onKeydown, false],
  ['paste', onPaste, false],
  ['dragenter', onDragEnter, false],
  ['dragover', onDragOver, false],
  ['dragleave', onDragLeave, false],
  ['drop', onDrop, false],
] as const;

watch(mode, (value) => document.body.classList.toggle(PINNED_BODY_CLASS, value === 'pinned'));
watch(chat.currentId, (id) => writeStorage(CONVERSATION_KEY, id));

onMounted(() => {
  mounted.value = true;
  for (const [type, listener, capture] of windowListeners) window.addEventListener(type, listener as EventListener, capture);
  const layout = readStorage(LAYOUT_KEY);
  pinPreferred.value = layout === 'pinned' || layout === 'pinned-closed';
  void loadMe().then(() => {
    // A pinned sidebar comes back on the next page load (not on phones, where it would cover the page).
    if (layout === 'pinned' && !locked.value && !window.matchMedia(PHONE_QUERY).matches) {
      mode.value = 'pinned';
      void loadHistory();
    }
  });
});

onBeforeUnmount(() => {
  for (const [type, listener, capture] of windowListeners) window.removeEventListener(type, listener as EventListener, capture);
  document.body.classList.remove(PINNED_BODY_CLASS);
  chat.stop();
});
</script>

<template>
  <div v-if="mounted" class="yx-ai" :class="`yx-ai--${mode}`">
    <button
      v-if="mode === 'collapsed'"
      ref="pill"
      type="button"
      class="yx-ai-pill"
      :class="{ 'is-locked': locked }"
      :aria-label="locked ? `${t.lockedLabel}: ${lockReason}` : t.pillLabel"
      :title="locked ? lockReason : t.pillLabel"
      @click="open"
    >
      <svg v-if="locked" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M7 10V7a5 5 0 0 1 10 0v3h1a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V11a1 1 0 0 1 1-1h1Zm2 0h6V7a3 3 0 0 0-6 0v3Z" /></svg>
      <svg v-else viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M12 2l2.1 5.9L20 10l-5.9 2.1L12 18l-2.1-5.9L4 10l5.9-2.1L12 2Zm6 12 1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3Z" /></svg>
      <span class="yx-ai-pill__text">{{ locked ? lockReason : t.pillText }}</span>
      <kbd v-if="!locked" class="yx-ai-pill__key">/</kbd>
    </button>
    <section v-else-if="me" ref="panel" class="yx-ai-panel" :role="mode === 'floating' ? 'dialog' : 'complementary'" :aria-label="t.panelLabel">
      <ConversationHeader
        :title="title"
        :list-open="listOpen"
        :pinned="mode === 'pinned'"
        :busy="chat.streaming.value"
        @toggle-list="toggleList"
        @new-conversation="newConversation"
        @toggle-pin="togglePin"
        @collapse="collapse"
      />
      <div class="yx-ai-body">
        <MessageList
          :messages="chat.messages.value"
          :draft="chat.draft.value"
          :status-text="chat.statusText.value"
          :streaming="chat.streaming.value"
          :loading="chat.messagesLoading.value"
          :failure-text="failureText"
          :can-retry="chat.canRetry.value"
          @stop="chat.stop"
          @retry="chat.retry(answerContext())"
        />
        <ConversationList
          v-if="listOpen"
          :conversations="chat.conversations.value"
          :current-id="chat.currentId.value"
          :loading="chat.listLoading.value"
          :load-error="chat.listError.value"
          :busy="chat.streaming.value"
          :rename="chat.rename"
          :remove="chat.remove"
          @select="selectConversation"
          @create="newConversation"
          @close="listOpen = false"
        />
      </div>
      <Composer
        ref="composer"
        v-model="draftText"
        :attachments="pending"
        :max-chars="me.limits.maxPromptChars"
        :busy="chat.streaming.value || chat.messagesLoading.value"
        :preparing="preparing > 0"
        :notice="notice"
        @submit="submit"
        @attach="addFiles"
        @remove="(key) => (pending = pending.filter((file) => file.key !== key))"
      />
    </section>
    <div v-if="dragDepth > 0 && mode !== 'collapsed'" class="yx-ai-drop" aria-hidden="true">
      <div class="yx-ai-drop__card">
        <strong>{{ t.dropTitle }}</strong>
        <span>{{ t.dropHint }}</span>
      </div>
    </div>
  </div>
</template>
