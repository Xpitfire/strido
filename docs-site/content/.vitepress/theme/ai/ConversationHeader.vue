<script setup lang="ts">
// Panel header: the open conversation's title (opens the conversation list), new conversation,
// pin to the side / float, and collapse to the pill.
import { useAiMessages } from './messages';

defineProps<{ title: string; listOpen: boolean; pinned: boolean; busy: boolean }>();
const emit = defineEmits<{ toggleList: []; newConversation: []; togglePin: []; collapse: [] }>();
const t = useAiMessages();
</script>

<template>
  <header class="yx-ai-header">
    <button
      type="button"
      class="yx-ai-header__title"
      :aria-expanded="listOpen"
      aria-controls="yx-ai-conversations"
      :title="listOpen ? t.hideConversations : t.showConversations"
      @click="emit('toggleList')"
    >
      <span class="yx-ai-header__text">{{ title }}</span>
      <svg class="yx-ai-header__chevron" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M7 10l5 5 5-5z" /></svg>
    </button>
    <button type="button" class="yx-ai-icon" :aria-label="t.newConversation" :title="`${t.newConversation} (Alt+N)`" :disabled="busy" @click="emit('newConversation')">
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6z" /></svg>
    </button>
    <button type="button" class="yx-ai-icon yx-ai-icon--pin" :aria-label="pinned ? t.unpin : t.pin" :title="pinned ? t.unpin : t.pin" :aria-pressed="pinned" @click="emit('togglePin')">
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M3 4h18v16H3V4Zm2 2v12h9V6H5Zm11 0v12h3V6h-3Z" /></svg>
    </button>
    <button type="button" class="yx-ai-icon" :aria-label="t.collapse" :title="`${t.collapse} (Esc)`" @click="emit('collapse')">
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M5 11h14v2H5z" /></svg>
    </button>
  </header>
</template>
