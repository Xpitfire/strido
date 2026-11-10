// node --test docs-site/scripts/ : the translation catalogue rules the German site depends on.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { publishedPages } from './pages.mjs';
import { mergeCatalogue, translationProblems } from './i18n-catalogues.mjs';
import { segmentKey, translateMarkdown, translationOf } from './i18n.mjs';

const catalogue = (pairs) => Object.fromEntries(pairs.map(([en, de]) => [segmentKey(en), { en, de }]));

test('an untranslated page renders back to the English source (only heading ids are added)', async () => {
  for (const page of await publishedPages()) {
    const rendered = translateMarkdown(page.text, {}).text.split('\n').map((line) => line.replace(/^(#{1,6} .*?) \{#[^}]+\}$/, '$1')); // drop added {#id}
    const source = page.text.split('\n').map((line) => (/^#{1,6} /.test(line) ? line.replace(/\s+$/, '') : line)); // headings lose trailing spaces
    assert.deepEqual(rendered, source, page.repositoryPath);
  }
});

test('German headings keep the English id, repeated headings are numbered like VitePress does', () => {
  const page = translateMarkdown('## Who uses it\n\ntext\n\n## Who uses it\n', catalogue([['Who uses it', 'Wer nutzt es']]));
  assert.equal(page.text, '## Wer nutzt es {#who-uses-it}\n\ntext\n\n## Wer nutzt es {#who-uses-it-1}\n');
});

test('changed numbers carry over into the translation, in German notation', () => {
  const entry = { en: 'The pack weighs 0.38 kg and costs €1,126.97 (2 cells).', de: 'Der Akku wiegt 0,38 kg und kostet 1.126,97 € (2 Zellen).' };
  assert.equal(translationOf(entry, 'The pack weighs 0.41 kg and costs €1,204.50 (2 cells).'), 'Der Akku wiegt 0,41 kg und kostet 1.204,50 € (2 Zellen).');
  assert.equal(translationOf(entry, 'The pack weighs 0.41 kg and costs €1,204.50 (2 cells) or 3.'), null); // a new number: retranslate
});

test('a number the translation wrote differently cannot be carried over: the segment needs a new translation', () => {
  assert.equal(translationOf({ en: 'Total 1126 g for 2 robots', de: 'Insgesamt 1.126 g für zwei Roboter' }, 'Total 1200 g for 2 robots'), null);
});

test('a table row whose numbers repeat still maps by position', () => {
  const entry = { en: '| M3 nut | 4 | 4 |', de: '| M3-Mutter | 4 | 4 |' };
  assert.equal(translationOf(entry, '| M3 nut | 2 | 4 |'), '| M3-Mutter | 2 | 4 |');
});

test('merging keeps translations in use, opens new segments and drops removed ones', () => {
  const previous = catalogue([['Old sentence.', 'Alter Satz.'], ['Kept 5 times.', '5-mal behalten.']]);
  const next = mergeCatalogue(previous, ['Kept 6 times.', 'New sentence.']);
  assert.deepEqual(Object.values(next).map((entry) => [entry.en, entry.de]), [['Kept 6 times.', '6-mal behalten.'], ['New sentence.', null]]);
});

test('the structure check finds broken Markdown, not prose with comparisons', () => {
  assert.deepEqual(translationProblems('Run `make verify` ([gate](x.md)).', 'Führen Sie `make verify` aus ([Prüfung](y.md)).'), ['link targets differ']);
  assert.deepEqual(translationProblems('| a | b |', '| a | b | c |'), ['table cells differ']);
  assert.deepEqual(translationProblems('roll < 0.5 rad, height > 0.1 m', 'Rollen < 0,5 rad, Höhe > 0,1 m'), []);
});
