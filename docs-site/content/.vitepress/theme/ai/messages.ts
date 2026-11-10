// Visible texts of the AI bar (English and German) and the plain-language wording of failures.
import { defineMessages } from '../i18n';
import { AssistantError } from './useAssistantApi';
import { AttachmentError } from './attachments';

const kib = (bytes: number) => `${Math.round(bytes / 1024)} KB`;
const mib = (bytes: number) => `${(bytes / 1048576).toFixed(1)} MB`;

const en = {
  panelLabel: 'Strido assistant',
  pillText: 'Ask Strido…',
  pillLabel: 'Ask the Strido assistant (shortcut /)',
  lockedLabel: 'Assistant unavailable',
  unreachable: 'The assistant is not reachable right now. Try again later.',
  newConversation: 'New conversation',
  showConversations: 'Show conversations',
  hideConversations: 'Hide conversations',
  pin: 'Pin to the side',
  unpin: 'Unpin',
  collapse: 'Collapse',
  conversations: 'Conversations',
  messageCount: (count: number) => (count === 1 ? '1 message' : `${count} messages`),
  noConversations: 'No conversations yet. Ask your first question below.',
  loading: 'Loading…',
  rename: 'Rename',
  renameLabel: 'Conversation title',
  save: 'Save',
  cancel: 'Cancel',
  delete: 'Delete',
  confirmDelete: 'Delete this conversation?',
  waitForAnswer: 'Wait for the answer or stop it first.',
  emptyTitle: 'Ask about Strido',
  emptyHint: 'Building, parts, wiring, software: answers come from this documentation and link their sources. Attach photos or files with the clip, by pasting or by dropping them here.',
  you: 'You',
  assistant: 'Assistant',
  sources: 'Sources',
  thinking: 'Thinking…',
  stop: 'Stop',
  retry: 'Retry',
  stopped: 'Stopped',
  failed: 'Not finished',
  copyCode: 'Copy code',
  copied: 'Copied',
  placeholder: 'Ask a question…',
  attach: 'Attach images or text files',
  remove: (name: string) => `Remove ${name}`,
  send: 'Send',
  composerHint: 'Enter sends · Shift+Enter new line',
  charsLeft: (count: number) => `${count} characters left`,
  preparing: 'Preparing attachments…',
  dropTitle: 'Drop to attach',
  dropHint: 'Images and text files',
  tooManyFiles: (max: number) => `At most ${max} attachments per message.`,
  unsupportedFile: (name: string) => `${name}: only images (PNG, JPEG, WebP, GIF) and text files (TXT, Markdown, CSV, JSON, YAML) can be attached.`,
  imageTooLarge: (name: string, max: number) => `${name} stays larger than ${mib(max)} even after shrinking.`,
  textTooLarge: (name: string, max: number) => `${name} is larger than ${kib(max)}.`,
  notText: (name: string) => `${name} is not a UTF-8 text file.`,
  unreadableImage: (name: string) => `${name} could not be read as an image.`,
  errorSignedOut: 'Your sign-in has expired. Reload the page to sign in again.',
  errorUnavailable: 'The assistant is not available for your account.',
  errorTooManyConversations: 'You have reached the maximum number of conversations. Delete an old one, then try again.',
  errorQuotaExceeded: 'Your stored attachments use all your space. Delete old conversations to attach more, or send without attachments.',
  errorNotFound: 'This conversation no longer exists.',
  errorBusy: 'Another answer is still being written. Wait for it or stop it, then try again.',
  errorTooLarge: 'The message or its attachments are too large. Remove an attachment or shorten the text.',
  errorMediaType: 'One of the attachments has a file type the assistant does not accept.',
  errorRateLimited: 'Too many questions in a short time. Wait a minute, then try again.',
  errorModelUnavailable: 'The language model is not available right now. Try again in a moment.',
  errorInvalid: 'The assistant did not accept this message. Shorten it or remove attachments.',
  errorOffline: 'The assistant cannot be reached. Check your connection.',
  errorBadResponse: 'The assistant sent an unexpected reply. Reload the page and try again.',
  errorInterrupted: 'The connection dropped before the answer was finished.',
  errorFailed: 'The answer could not be finished.',
};

type AiMessages = typeof en;

const de: AiMessages = {
  panelLabel: 'Strido-Assistent',
  pillText: 'Strido fragen…',
  pillLabel: 'Den Strido-Assistenten fragen (Kürzel /)',
  lockedLabel: 'Assistent nicht verfügbar',
  unreachable: 'Der Assistent ist gerade nicht erreichbar. Bitte später erneut versuchen.',
  newConversation: 'Neue Unterhaltung',
  showConversations: 'Unterhaltungen anzeigen',
  hideConversations: 'Unterhaltungen ausblenden',
  pin: 'Seitlich anheften',
  unpin: 'Lösen',
  collapse: 'Einklappen',
  conversations: 'Unterhaltungen',
  messageCount: (count: number) => (count === 1 ? '1 Nachricht' : `${count} Nachrichten`),
  noConversations: 'Noch keine Unterhaltungen. Stelle unten deine erste Frage.',
  loading: 'Wird geladen…',
  rename: 'Umbenennen',
  renameLabel: 'Titel der Unterhaltung',
  save: 'Speichern',
  cancel: 'Abbrechen',
  delete: 'Löschen',
  confirmDelete: 'Diese Unterhaltung löschen?',
  waitForAnswer: 'Warte auf die Antwort oder stoppe sie zuerst.',
  emptyTitle: 'Frag zu Strido',
  emptyHint: 'Aufbau, Teile, Verkabelung, Software: Die Antworten stammen aus dieser Dokumentation und verlinken ihre Quellen. Fotos oder Dateien hängst du mit der Büroklammer, per Einfügen oder per Ablegen an.',
  you: 'Du',
  assistant: 'Assistent',
  sources: 'Quellen',
  thinking: 'Denkt nach…',
  stop: 'Stopp',
  retry: 'Erneut versuchen',
  stopped: 'Gestoppt',
  failed: 'Nicht fertig',
  copyCode: 'Code kopieren',
  copied: 'Kopiert',
  placeholder: 'Frage stellen…',
  attach: 'Bilder oder Textdateien anhängen',
  remove: (name: string) => `${name} entfernen`,
  send: 'Senden',
  composerHint: 'Enter sendet · Umschalt+Enter neue Zeile',
  charsLeft: (count: number) => `noch ${count} Zeichen`,
  preparing: 'Anhänge werden vorbereitet…',
  dropTitle: 'Zum Anhängen ablegen',
  dropHint: 'Bilder und Textdateien',
  tooManyFiles: (max: number) => `Höchstens ${max} Anhänge pro Nachricht.`,
  unsupportedFile: (name: string) => `${name}: Angehängt werden können nur Bilder (PNG, JPEG, WebP, GIF) und Textdateien (TXT, Markdown, CSV, JSON, YAML).`,
  imageTooLarge: (name: string, max: number) => `${name} bleibt auch verkleinert größer als ${mib(max)}.`,
  textTooLarge: (name: string, max: number) => `${name} ist größer als ${kib(max)}.`,
  notText: (name: string) => `${name} ist keine UTF-8-Textdatei.`,
  unreadableImage: (name: string) => `${name} konnte nicht als Bild gelesen werden.`,
  errorSignedOut: 'Deine Anmeldung ist abgelaufen. Lade die Seite neu, um dich wieder anzumelden.',
  errorUnavailable: 'Der Assistent ist für dein Konto nicht verfügbar.',
  errorTooManyConversations: 'Du hast die Höchstzahl an Unterhaltungen erreicht. Lösche eine alte und versuche es dann erneut.',
  errorQuotaExceeded: 'Deine gespeicherten Anhänge belegen deinen ganzen Platz. Lösche alte Unterhaltungen, um mehr anzuhängen, oder sende ohne Anhänge.',
  errorNotFound: 'Diese Unterhaltung gibt es nicht mehr.',
  errorBusy: 'Eine andere Antwort wird noch geschrieben. Warte darauf oder stoppe sie und versuche es dann erneut.',
  errorTooLarge: 'Die Nachricht oder ihre Anhänge sind zu groß. Entferne einen Anhang oder kürze den Text.',
  errorMediaType: 'Einer der Anhänge hat einen Dateityp, den der Assistent nicht annimmt.',
  errorRateLimited: 'Zu viele Fragen in kurzer Zeit. Warte eine Minute und versuche es dann erneut.',
  errorModelUnavailable: 'Das Sprachmodell ist gerade nicht verfügbar. Versuche es gleich noch einmal.',
  errorInvalid: 'Der Assistent hat diese Nachricht nicht angenommen. Kürze sie oder entferne Anhänge.',
  errorOffline: 'Der Assistent ist nicht erreichbar. Prüfe deine Verbindung.',
  errorBadResponse: 'Der Assistent hat unerwartet geantwortet. Lade die Seite neu und versuche es erneut.',
  errorInterrupted: 'Die Verbindung brach ab, bevor die Antwort fertig war.',
  errorFailed: 'Die Antwort konnte nicht fertiggestellt werden.',
};

export const useAiMessages = defineMessages({ en, de });

const STATUS_TEXT: Record<number, keyof AiMessages> = {
  400: 'errorInvalid',
  401: 'errorSignedOut',
  403: 'errorUnavailable',
  404: 'errorNotFound',
  409: 'errorBusy',
  413: 'errorTooLarge',
  415: 'errorMediaType',
  429: 'errorRateLimited',
  503: 'errorModelUnavailable',
};

// Codes produced by the client itself, sent in a stream `error` event (status 0) or more specific
// than their HTTP status.
const CODE_TEXT: Record<string, keyof AiMessages> = {
  network: 'errorOffline',
  bad_response: 'errorBadResponse',
  stream_ended: 'errorInterrupted',
  rate_limited: 'errorRateLimited',
  model_unavailable: 'errorModelUnavailable',
  overloaded: 'errorModelUnavailable',
  too_large: 'errorTooLarge',
  too_many_conversations: 'errorTooManyConversations',
  quota_exceeded: 'errorQuotaExceeded',
};

/** One sentence a reader understands, for any failure of the API or of preparing an attachment. */
export function describeError(error: unknown, t: AiMessages): string {
  if (error instanceof AttachmentError) {
    if (error.reason === 'type') return t.unsupportedFile(error.fileName);
    if (error.reason === 'image-size') return t.imageTooLarge(error.fileName, error.limit);
    if (error.reason === 'text-size') return t.textTooLarge(error.fileName, error.limit);
    if (error.reason === 'encoding') return t.notText(error.fileName);
    return t.unreadableImage(error.fileName);
  }
  if (error instanceof AssistantError) {
    const key = CODE_TEXT[error.code] ?? STATUS_TEXT[error.status] ?? 'errorFailed';
    return t[key] as string;
  }
  return t.errorFailed;
}
