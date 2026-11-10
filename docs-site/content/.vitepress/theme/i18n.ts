// UI texts of the theme components per site language. Each component module declares its messages
// with defineMessages({ en: {...}, de: {...} }) (German must have every English key) and reads them
// with the returned composable; localePath() keeps links inside the reader's language.
import { computed } from 'vue';
import { useData } from 'vitepress';

export type Locale = 'en' | 'de';

export function useLocale() {
  const { lang } = useData();
  return computed<Locale>(() => (lang.value.startsWith('de') ? 'de' : 'en'));
}

export function defineMessages<T extends Record<string, string | ((...args: never[]) => string)>>(messages: { en: T; de: T }) {
  return function useMessages() {
    const locale = useLocale();
    return computed(() => messages[locale.value]);
  };
}

export function localePath(path: string, locale: Locale): string {
  // '/docs/shop' -> '/de/docs/shop' on the German site; files (images, data, downloads) stay shared.
  return locale === 'de' && /^\/(docs|requirements)(\/|$|#|\?)/.test(path) ? `/de${path}` : path;
}

export function useLocalePath() {
  const locale = useLocale();
  return (path: string) => localePath(path, locale.value);
}

export function dataUrl(path: string, locale: Locale): string {
  // Translated runtime data: '/bom/products.json' -> '/bom/products.de.json' on the German site.
  return locale === 'de' ? path.replace(/\.json$/, '.de.json') : path;
}

export function formatMoney(amount: number, locale: Locale): string {
  return new Intl.NumberFormat(locale === 'de' ? 'de-AT' : 'en-GB', { style: 'currency', currency: 'EUR' }).format(amount);
}
