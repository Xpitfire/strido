// Heading ids shared by the VitePress config and the translation renderer (German headings keep the
// English id, so every deep link and anchor works in both languages).
//
// VitePress' default slug rule, plus en/em dashes count as separators (the default kept them:
// "step-6-–-servo-ubecs"), and assembly steps get a stable id by number ("Step 6 – ..." -> "step-6")
// so parts, shop and catalogue can link to /docs/assembly/#step-6.
export function slugify(text) {
  // "Step <number> – <title>" at the start of a heading (en dash, em dash or hyphen).
  const step = text.match(/^Step (\d+) [–—-] /);
  if (step) return `step-${step[1]}`;
  return text
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // combining accents left by NFKD
    .replace(/[\u0000-\u001f]/g, '') // control characters
    .replace(/[\s~`!@#$%^&*()\-_+=[\]{}|\\;:"'“”‘’<>,.?/–—]+/g, '-') // runs of spaces/punctuation/dashes -> one '-'
    .replace(/^-+|-+$/g, '') // no leading/trailing '-'
    .replace(/^(\d)/, '_$1') // ids must not start with a digit
    .toLowerCase();
}

// The text VitePress slugs is the rendered heading: drop Markdown link targets and HTML tags first.
export function headingText(markdown) {
  return markdown
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1') // [text](url) and ![alt](src) -> their text
    .replace(/<[^>]+>/g, '') // inline HTML tags
    .trim();
}
