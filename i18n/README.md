# Translations of the documentation site

`i18n/<locale>/<repository path>.json` holds one catalogue per published page (`docs/**`, `requirements/**`, the print list), the home page (`site/home.md.json`) and the runtime data the theme reads (`data/<public path>.json`). Each entry maps an English segment (paragraph, list item, table row, heading, diagram) to its translation:

```json
{ "3f1c0a9b7d2e4f60": { "en": "English segment", "de": "Deutsche Übersetzung" } }
```

`docs-site/scripts/sync-docs.mjs` renders `/de/...` from the current English page and this catalogue; generated pages (assembly manual, BOM, verification reports) keep their translation when they are regenerated, and changed numbers carry over. A segment without a translation shows in English and the page says it is partly translated.

## Workflow

1. Change the English source (or regenerate it).
2. `make i18n`: adds new segments with `"de": null` and drops unused ones.
3. Translate every `"de": null` entry (an entry with `"stale"` shows the previous translation whose numbers no longer matched).
4. `make drift` (part of `make check-fast`) fails while a segment is untranslated or a translation breaks the Markdown structure (code spans, math, link targets, HTML tags, table cells, line count).

## German style

- Formal "Sie" in instructions; concise technical German; German decimals in prose and tables (0,71; 1.126,97 €), never inside code, math, links, part numbers or thread sizes (M2.5).
- Keep identifiers, product and brand names, units and the `[ASSUMED]`/`[MEASURE]`/`[UNVERIFIED]` tags exactly.
- **Established English technical terms stay English**; do not force a German word: Reinforcement Learning, Policy, Reward, Observation, Action, Value Function, Advantage, Domain Randomization, Domain Adaptation, Sim-to-Real, State Estimation, Gait, Trot, Controller (software), Node/Topic/Service/Message/Launch-File (ROS 2), Container, Image, Firmware, Watchdog, Slicer, Shop, Arming-Port, Loop-Key, Power-Monitor.
- Established German terms stay German: Kinematik, Vorwärtskinematik, inverse Kinematik, Koppelgetriebe, Freiheitsgrade, Kabelbaum, Spannungsregler, Sicherung, Abstandsbolzen, Sicherungsmutter, Schraubensicherung, Blockiermoment, Prüfung (verification checks), Warenkorb, Druckpaket, Montageanleitung, Stückliste, Standphase/Schwungphase.
- The status words of check tables (`ok`, `warn`, `fail`) stay as they are.
