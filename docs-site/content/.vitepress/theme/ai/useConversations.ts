// Conversation state of the AI bar: the reader's conversation list, the open conversation's messages,
// and the answer being streamed (status line, growing text, stop and retry).
import { computed, ref, shallowRef } from 'vue';
import type { PendingAttachment } from './attachments';
import { AssistantError, assistantApi, type AnswerContext, type Conversation, type StoredAttachment, type Message, type StreamHandlers } from './useAssistantApi';

/** A stored attachment, with the local image preview while it is fresh from this browser. */
export interface ViewAttachment extends StoredAttachment {
  previewUrl?: string;
}

export interface ViewMessage extends Omit<Message, 'attachments'> {
  attachments: ViewAttachment[];
  /** True for the optimistic copy of a question the server has not confirmed yet. */
  local?: boolean;
}

export interface Question {
  text: string;
  attachments: PendingAttachment[];
  context: AnswerContext;
}

type AnswerHandlers = Omit<StreamHandlers, 'status' | 'delta' | 'done'>;

let localId = 0;

export function useConversations() {
  const conversations = ref<Conversation[]>([]);
  const listLoading = ref(false);
  const listError = shallowRef<unknown>(null);
  /** null: a new conversation the server creates with the first question. */
  const currentId = ref<string | null>(null);
  const messages = ref<ViewMessage[]>([]);
  const messagesLoading = ref(false);
  const streaming = ref(false);
  const statusText = ref('');
  /** Text of the answer being streamed (null while none is). */
  const draft = ref<string | null>(null);
  /** The last failure of loading or sending, shown with Retry where that helps. */
  const failure = shallowRef<unknown>(null);
  /** The last question sent from this page, kept until the server has stored it. */
  const unsentQuestion = shallowRef<Question | null>(null);
  let controller: AbortController | null = null;
  let loadSerial = 0;
  let pendingDelta = '';
  let flushFrame = 0;

  const current = computed(() => conversations.value.find((conversation) => conversation.id === currentId.value) ?? null);
  /**
   * Retry resends a question the server never stored; for a stored one it asks the server to answer the
   * last question again (after a failure, a stop, or a question left without an answer).
   */
  const canRetry = computed(() => {
    if (streaming.value) return false;
    const last = messages.value.at(-1);
    if (!last) return false;
    if (last.local) return unsentQuestion.value !== null;
    if (!currentId.value || !messages.value.some((message) => message.role === 'user')) return false;
    return failure.value !== null || last.role === 'user' || last.status !== 'complete';
  });

  async function refresh() {
    listLoading.value = true;
    try {
      conversations.value = await assistantApi.conversations();
      listError.value = null;
    } catch (error) {
      listError.value = error;
    } finally {
      listLoading.value = false;
    }
  }

  async function select(id: string) {
    if (streaming.value) return;
    const serial = ++loadSerial;
    currentId.value = id;
    messages.value = [];
    failure.value = null;
    unsentQuestion.value = null;
    messagesLoading.value = true;
    try {
      const loaded = await assistantApi.messages(id);
      if (serial === loadSerial) messages.value = loaded;
    } catch (error) {
      if (serial === loadSerial) failure.value = error;
    } finally {
      if (serial === loadSerial) messagesLoading.value = false;
    }
  }

  function startNew() {
    if (streaming.value) return;
    loadSerial++;
    currentId.value = null;
    messages.value = [];
    messagesLoading.value = false;
    failure.value = null;
    unsentQuestion.value = null;
  }

  async function rename(id: string, title: string) {
    const renamed = await assistantApi.rename(id, title);
    conversations.value = conversations.value.map((conversation) => (conversation.id === id ? renamed : conversation));
  }

  async function remove(id: string) {
    await assistantApi.remove(id);
    conversations.value = conversations.value.filter((conversation) => conversation.id !== id);
    if (currentId.value !== id) return;
    const newest = conversations.value[0];
    if (newest) await select(newest.id);
    else startNew();
  }

  function flushDelta() {
    cancelAnimationFrame(flushFrame);
    flushFrame = 0;
    if (pendingDelta && draft.value !== null) draft.value += pendingDelta;
    pendingDelta = '';
  }

  /** Streams one answer into the draft; a stop or failure keeps the partial text as a message. */
  async function answer(start: (handlers: StreamHandlers, signal: AbortSignal) => Promise<void>, extra: AnswerHandlers) {
    failure.value = null;
    streaming.value = true;
    statusText.value = '';
    draft.value = '';
    controller = new AbortController();
    try {
      await start(
        {
          ...extra,
          status(text) {
            statusText.value = text;
          },
          delta(text) {
            pendingDelta += text;
            if (!flushFrame) flushFrame = requestAnimationFrame(flushDelta);
          },
          done(message) {
            flushDelta();
            draft.value = null;
            messages.value.push(message);
          },
        },
        controller.signal,
      );
    } catch (error) {
      const stopped = error instanceof AssistantError && error.code === 'aborted';
      flushDelta();
      if (draft.value) {
        const status = stopped ? 'stopped' : 'error';
        messages.value.push({ id: `local-${++localId}`, role: 'assistant', text: draft.value, status, attachments: [], sources: [], createdAt: new Date().toISOString() });
      }
      if (!stopped) failure.value = error;
    } finally {
      draft.value = null;
      streaming.value = false;
      statusText.value = '';
      controller = null;
    }
    void refresh(); // picks up the server's title and message count
  }

  async function send(question: Question) {
    // Sending waits for the open conversation to load (the composer is disabled meanwhile), so the
    // question never lands in a list that the loaded messages then replace.
    if (streaming.value || messagesLoading.value) return;
    unsentQuestion.value = question;
    const optimistic: ViewMessage = {
      id: `local-${++localId}`,
      role: 'user',
      text: question.text,
      status: 'complete',
      attachments: question.attachments.map((file) => ({ id: '', name: file.name, mediaType: file.mediaType, size: file.size, previewUrl: file.previewUrl })),
      sources: [],
      createdAt: new Date().toISOString(),
      local: true,
    };
    messages.value.push(optimistic);
    const body = {
      text: question.text,
      attachments: question.attachments.map(({ name, mediaType, data }) => ({ name, mediaType, data })),
      ...question.context,
    };
    await answer((handlers, signal) => assistantApi.send(currentId.value ?? 'new', body, handlers, signal), {
      conversation(conversation) {
        currentId.value = conversation.id;
        conversations.value = [conversation, ...conversations.value.filter((known) => known.id !== conversation.id)];
      },
      user(message) {
        unsentQuestion.value = null;
        const index = messages.value.findIndex((known) => known.id === optimistic.id);
        const stored: ViewMessage = {
          ...message,
          attachments: message.attachments.map((file, i) => ({ ...file, previewUrl: optimistic.attachments[i]?.previewUrl })),
        };
        if (index >= 0) messages.value.splice(index, 1, stored);
      },
    });
  }

  function stop() {
    controller?.abort();
  }

  /** `context` (language, page) applies when the server answers a stored question again. */
  async function retry(context: AnswerContext) {
    if (!canRetry.value) return;
    const last = messages.value.at(-1);
    const question = unsentQuestion.value;
    if (last?.local && question) {
      messages.value.pop();
      await send(question);
      return;
    }
    const id = currentId.value;
    if (!id) return;
    // The server drops the answers after the last question before answering it again; so does the view.
    const lastQuestion = messages.value.findLastIndex((message) => message.role === 'user');
    messages.value.splice(lastQuestion + 1);
    await answer((handlers, signal) => assistantApi.regenerate(id, context, handlers, signal), {
      conversation(conversation) {
        conversations.value = conversations.value.map((known) => (known.id === conversation.id ? conversation : known));
      },
    });
  }

  return {
    conversations,
    listLoading,
    listError,
    currentId,
    current,
    messages,
    messagesLoading,
    streaming,
    statusText,
    draft,
    failure,
    canRetry,
    refresh,
    select,
    startNew,
    rename,
    remove,
    send,
    stop,
    retry,
  };
}
