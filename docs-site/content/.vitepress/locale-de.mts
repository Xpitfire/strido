// German site (/de/): navigation, theme labels and search texts. The pages themselves are rendered by
// docs-site/scripts/sync-docs.mjs from the translation catalogues in i18n/de/.
import type { DefaultTheme, LocaleSpecificConfig } from 'vitepress';

export function germanSite(sidebar: DefaultTheme.Sidebar) {
  return {
    label: 'Deutsch',
    lang: 'de-AT',
    link: '/de/',
    title: 'Strido',
    description: 'Offener Vierbeiner mit 12 Freiheitsgraden: druckbares CAD, geprüfte Montage, Teilekatalog, Firmware, ROS 2, Simulation und Training.',
    themeConfig: {
      nav: [
        { text: 'Erste Schritte', link: '/de/docs/getting-started' },
        { text: 'Shop', link: '/de/docs/shop' },
        { text: 'Druckpaket', link: '/de/docs/print-kit' },
        { text: '3D-Ansicht', link: '/de/docs/viewer' },
        { text: 'Lernen', link: '/de/docs/wiki/', activeMatch: '^/de/docs/wiki/' },
        {
          text: 'Doku',
          items: [
            { text: 'Teilekatalog', link: '/de/docs/catalog' },
            { text: 'Montageanleitung', link: '/de/docs/assembly/' },
            { text: 'Elektronik, Verkabelung und Stromversorgung', link: '/de/docs/electronics' },
            { text: 'Software', link: '/de/docs/software' },
            { text: 'Simulation und Lernen', link: '/de/docs/simulation' },
            { text: 'Verifikation', link: '/de/docs/verification' },
            { text: 'Downloads', link: '/de/docs/downloads' },
            { text: 'KI-Assistent und Agenten', link: '/de/docs/ai' },
          ],
        },
      ],
      sidebar,
      outline: { level: [2, 3], label: 'Auf dieser Seite' },
      docFooter: { prev: 'Vorherige Seite', next: 'Nächste Seite' },
      footer: {
        message: 'MIT-Lizenz. Mechanik abgeleitet von Yertle (Jerome Graves). CAD, Simulation und native Tests sind kein Hardware-Nachweis – siehe <a href="/de/docs/verification">Verifikation</a>.',
        copyright: 'Strido',
      },
      langMenuLabel: 'Sprache wechseln',
      returnToTopLabel: 'Nach oben',
      sidebarMenuLabel: 'Menü',
      darkModeSwitchLabel: 'Darstellung',
      lightModeSwitchTitle: 'Zum hellen Design wechseln',
      darkModeSwitchTitle: 'Zum dunklen Design wechseln',
      skipToContentLabel: 'Zum Inhalt springen',
      notFound: {
        title: 'SEITE NICHT GEFUNDEN',
        quote: 'Diese Seite gibt es nicht, oder sie ist umgezogen.',
        linkLabel: 'Zur Startseite',
        linkText: 'Zur Startseite',
      },
    },
    search: {
      translations: {
        button: { buttonText: 'Suchen', buttonAriaLabel: 'Suchen' },
        modal: {
          displayDetails: 'Details anzeigen',
          resetButtonTitle: 'Suche zurücksetzen',
          backButtonTitle: 'Suche schließen',
          noResultsText: 'Keine Treffer für',
          footer: { selectText: 'auswählen', navigateText: 'navigieren', closeText: 'schließen' },
        },
      },
    },
  } satisfies LocaleSpecificConfig<DefaultTheme.Config> & { label: string; link: string; search: object };
}
