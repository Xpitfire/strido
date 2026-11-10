<script setup lang="ts">
// The reader's conversations, newest first: switch, start a new one, rename inline, delete with an
// inline confirmation. Esc steps back one layer (rename, confirmation, then the list itself).
import { nextTick, ref } from 'vue';
import { useLocale } from '../i18n';
import { describeError, useAiMessages } from './messages';
import type { Conversation } from './useAssistantApi';

const TITLE_MAX = 120;

const props = defineProps<{
  conversations: Conversation[];
  currentId: string | null;
  loading: boolean;
  loadError: unknown;
  busy: boolean;
  rename: (id: string, title: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
}>();
const emit = defineEmits<{ select: [id: string]; create: []; close: [] }>();
const t = useAiMessages();
const locale = useLocale();
const editingId = ref<string | null>(null);
const editTitle = ref('');
const confirmingId = ref<string | null>(null);
const actionError = ref('');
const working = ref(false);
const editInput = ref<HTMLInputElement[]>([]);

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(locale.value === 'de' ? 'de-AT' : 'en-GB', { dateStyle: 'medium' }).format(new Date(iso));
}

async function startRename(conversation: Conversation) {
  confirmingId.value = null;
  editingId.value = conversation.id;
  editTitle.value = conversation.title;
  await nextTick();
  editInput.value[0]?.select();
}

async function run(action: () => Promise<void>) {
  working.value = true;
  actionError.value = '';
  try {
    await action();
    editingId.value = null;
    confirmingId.value = null;
  } catch (error) {
    actionError.value = describeError(error, t.value);
  } finally {
    working.value = false;
  }
}

function saveRename(id: string) {
  const title = editTitle.value.trim().slice(0, TITLE_MAX);
  if (!title) return;
  void run(() => props.rename(id, title));
}

function onEscape(event: KeyboardEvent) {
  event.stopPropagation();
  if (editingId.value) editingId.value = null;
  else if (confirmingId.value) confirmingId.value = null;
  else emit('close');
}
</script>

<template>
  <div id="yx-ai-conversations" class="yx-ai-list" role="region" :aria-label="t.conversations" @keydown.esc="onEscape">
    <button type="button" class="yx-ai-list__new" :disabled="busy" :title="busy ? t.waitForAnswer : undefined" @click="emit('create')">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6z" /></svg>
      {{ t.newConversation }}
    </button>
    <p v-if="actionError" class="yx-ai-list__error" role="alert">{{ actionError }}</p>
    <p v-if="loading && !conversations.length" class="yx-ai-list__note">{{ t.loading }}</p>
    <p v-else-if="loadError" class="yx-ai-list__error" role="alert">{{ describeError(loadError, t) }}</p>
    <p v-else-if="!conversations.length" class="yx-ai-list__note">{{ t.noConversations }}</p>
    <ul v-else class="yx-ai-list__items">
      <li v-for="conversation in conversations" :key="conversation.id" class="yx-ai-list__row" :class="{ 'is-current': conversation.id === currentId }">
        <form v-if="editingId === conversation.id" class="yx-ai-list__rename" @submit.prevent="saveRename(conversation.id)">
          <input ref="editInput" v-model="editTitle" :aria-label="t.renameLabel" :maxlength="TITLE_MAX" required />
          <button type="submit" class="yx-ai-list__action" :disabled="working || !editTitle.trim()">{{ t.save }}</button>
          <button type="button" class="yx-ai-list__action" @click="editingId = null">{{ t.cancel }}</button>
        </form>
        <div v-else-if="confirmingId === conversation.id" class="yx-ai-list__confirm" role="group" :aria-label="t.confirmDelete">
          <span>{{ t.confirmDelete }}</span>
          <button type="button" class="yx-ai-list__action yx-ai-list__action--danger" :disabled="working" @click="run(() => remove(conversation.id))">{{ t.delete }}</button>
          <button type="button" class="yx-ai-list__action" @click="confirmingId = null">{{ t.cancel }}</button>
        </div>
        <template v-else>
          <button
            type="button"
            class="yx-ai-list__open"
            :aria-current="conversation.id === currentId ? 'true' : undefined"
            :disabled="busy && conversation.id !== currentId"
            :title="busy && conversation.id !== currentId ? t.waitForAnswer : undefined"
            @click="emit('select', conversation.id)"
          >
            <span class="yx-ai-list__title">{{ conversation.title || t.newConversation }}</span>
            <span class="yx-ai-list__meta">{{ t.messageCount(conversation.messageCount) }} · {{ formatDate(conversation.updatedAt) }}</span>
          </button>
          <button type="button" class="yx-ai-icon" :aria-label="`${t.rename}: ${conversation.title}`" :title="t.rename" @click="startRename(conversation)">
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M4 17.25V20h2.75L17.8 8.94l-2.75-2.75L4 17.25Zm15.7-10.2a1 1 0 0 0 0-1.42l-1.33-1.33a1 1 0 0 0-1.42 0l-1.04 1.04 2.75 2.75 1.04-1.04Z" /></svg>
          </button>
          <button
            type="button"
            class="yx-ai-icon"
            :aria-label="`${t.delete}: ${conversation.title}`"
            :title="busy && conversation.id === currentId ? t.waitForAnswer : t.delete"
            :disabled="busy && conversation.id === currentId"
            @click="(editingId = null), (confirmingId = conversation.id)"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M9 3h6l1 2h4v2H4V5h4l1-2Zm-3 6h12l-1 12H7L6 9Z" /></svg>
          </button>
        </template>
      </li>
    </ul>
  </div>
</template>
