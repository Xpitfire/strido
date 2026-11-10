// The knowledge tools, one implementation for the chat model and the MCP endpoint: their JSON input
// schemas, a validator for the subset of JSON Schema they use, and the calls into the knowledge base.
// Links are site-relative for the chat (the site renders them) and absolute for MCP clients.

const LANGUAGE = { type: 'string', enum: ['en', 'de'], description: 'Language of the docs: en (default) or de.' };

export const TOOLS = [
  {
    name: 'search_docs',
    description:
      'Full-text search over the Strido documentation (build docs, electronics, assembly, verification, BOM, requirements and the Learn wiki). Returns ranked sections with title, section, url and a snippet. Use short keyword queries.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', minLength: 1, maxLength: 500, description: 'Keywords to search for.' },
        language: LANGUAGE,
        limit: { type: 'integer', minimum: 1, maximum: 10, description: 'Number of results (default 5).' },
      },
      required: ['query'],
      additionalProperties: false,
    },
  },
  {
    name: 'read_page',
    description:
      'Read a documentation page as Markdown, or one section of it by heading id (the part after # in a search result url). Long pages are cut at 40,000 characters with the list of section ids.',
    inputSchema: {
      type: 'object',
      properties: {
        url_or_path: { type: 'string', minLength: 1, maxLength: 500, description: 'Page URL or path, e.g. /docs/electronics or /docs/electronics#wiring-list.' },
        section: { type: 'string', maxLength: 200, description: 'Heading id of one section.' },
        language: LANGUAGE,
      },
      required: ['url_or_path'],
      additionalProperties: false,
    },
  },
  {
    name: 'list_pages',
    description: 'The site navigation (sidebar): every documentation page with its title and URL, grouped by section.',
    inputSchema: {
      type: 'object',
      properties: { language: LANGUAGE },
      additionalProperties: false,
    },
  },
  {
    name: 'search_parts',
    description:
      'Search the bill of materials: purchased parts (name, quantity, price and shop of buying plan A, summary, role, key specs) and printed parts, each with its product page URL.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', minLength: 1, maxLength: 300, description: 'Part name or keywords, e.g. "fuse" or "servo".' },
        language: LANGUAGE,
      },
      required: ['query'],
      additionalProperties: false,
    },
  },
];

const TOOLS_BY_NAME = new Map(TOOLS.map((tool) => [tool.name, tool]));

/** The first problem with `value` against `schema` (the subset these tools use), or null. */
export function validate(schema, value, at = 'input') {
  switch (schema.type) {
    case 'object': {
      if (value === null || typeof value !== 'object' || Array.isArray(value)) return `${at} must be an object`;
      for (const name of schema.required ?? []) if (value[name] === undefined) return `${at}.${name} is required`;
      for (const [name, item] of Object.entries(value)) {
        const property = schema.properties?.[name];
        if (property === undefined) {
          if (schema.additionalProperties === false) return `${at}.${name} is not a known property`;
          continue;
        }
        const problem = validate(property, item, `${at}.${name}`);
        if (problem !== null) return problem;
      }
      return null;
    }
    case 'string':
      if (typeof value !== 'string') return `${at} must be a string`;
      if (schema.enum !== undefined && !schema.enum.includes(value)) return `${at} must be one of ${schema.enum.join(', ')}`;
      if (value.length < (schema.minLength ?? 0)) return `${at} must not be empty`;
      if (value.length > (schema.maxLength ?? Infinity)) return `${at} is longer than ${schema.maxLength} characters`;
      return null;
    case 'integer':
      if (!Number.isInteger(value)) return `${at} must be an integer`;
      if (value < (schema.minimum ?? -Infinity) || value > (schema.maximum ?? Infinity)) {
        return `${at} must be between ${schema.minimum} and ${schema.maximum}`;
      }
      return null;
    default:
      return null;
  }
}

/**
 * Run a tool. Returns `{text, isError}`; bad input and unknown pages are errors the caller reports
 * to the model or the MCP client, never exceptions.
 * @param context.base '' for site-relative links, or the site URL for absolute ones
 * @param context.language the default language when the input names none
 */
export function runTool(knowledge, name, input, { base = '', language = 'en' } = {}) {
  const tool = TOOLS_BY_NAME.get(name);
  if (tool === undefined) return { text: `Unknown tool: ${name}`, isError: true };
  const args = input ?? {};
  const problem = validate(tool.inputSchema, args);
  if (problem !== null) return { text: `Invalid input: ${problem}`, isError: true };
  const lang = args.language ?? language;

  switch (name) {
    case 'search_docs': {
      const results = knowledge.search(args.query, { language: lang, limit: args.limit ?? 5, base });
      return { text: results.length === 0 ? 'No matching sections.' : JSON.stringify(results, null, 1), isError: false };
    }
    case 'read_page': {
      const page = knowledge.readPage(args.url_or_path, { section: args.section ?? '', language: args.language, base });
      if (page === null) return { text: `No page at ${args.url_or_path}. Use list_pages or search_docs.`, isError: true };
      return { text: `# ${page.title}\nURL: ${page.url}\n\n${page.markdown}`, isError: false };
    }
    case 'list_pages':
      return { text: JSON.stringify(knowledge.listPages({ language: lang, base }), null, 1), isError: false };
    case 'search_parts': {
      const parts = knowledge.parts.search(args.query, { language: lang, base });
      return { text: parts.length === 0 ? 'No matching parts.' : JSON.stringify(parts, null, 1), isError: false };
    }
  }
}
