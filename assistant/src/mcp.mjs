// MCP over Streamable HTTP, stateless with JSON responses: each POST carries one JSON-RPC 2.0 message
// and gets its answer (or 202 for a notification). The tools are the knowledge tools the chat model
// uses, with absolute site URLs; bad tool input is an `isError` result, not a protocol error.

import { runTool, TOOLS } from './tools.mjs';

export const SUPPORTED_PROTOCOL_VERSIONS = ['2025-06-18', '2025-03-26', '2024-11-05'];

const RPC = { PARSE_ERROR: -32700, INVALID_REQUEST: -32600, METHOD_NOT_FOUND: -32601, INVALID_PARAMS: -32602 };

const INSTRUCTIONS =
  'Strido documentation: search_docs for sections, read_page for a page or section, list_pages for the navigation, search_parts for the bill of materials. Pages exist in English (en) and German (de).';

function rpcError(id, code, message) {
  return { jsonrpc: '2.0', id: id ?? null, error: { code, message } };
}

export function parseError() {
  return rpcError(null, RPC.PARSE_ERROR, 'Parse error');
}

/**
 * Answer one JSON-RPC message; null for a notification (no answer is due).
 * @param context `{knowledge, siteUrl, version}`
 */
export function handleMcp(message, { knowledge, siteUrl, version }) {
  if (message === null || typeof message !== 'object' || Array.isArray(message) ||
      message.jsonrpc !== '2.0' || typeof message.method !== 'string') {
    return rpcError(message?.id, RPC.INVALID_REQUEST, 'Invalid Request: send one JSON-RPC 2.0 message per POST.');
  }
  const { id, method } = message;
  const params = message.params ?? {};
  if (id === undefined) return null; // notifications, e.g. notifications/initialized
  const result = (value) => ({ jsonrpc: '2.0', id, result: value });

  switch (method) {
    case 'initialize': {
      const requested = params.protocolVersion;
      return result({
        protocolVersion: SUPPORTED_PROTOCOL_VERSIONS.includes(requested) ? requested : SUPPORTED_PROTOCOL_VERSIONS[0],
        capabilities: { tools: {} },
        serverInfo: { name: 'strido', version },
        instructions: INSTRUCTIONS,
      });
    }
    case 'ping':
      return result({});
    case 'tools/list':
      return result({ tools: TOOLS.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })) });
    case 'tools/call': {
      if (typeof params.name !== 'string') return rpcError(id, RPC.INVALID_PARAMS, 'params.name must be a tool name');
      if (!TOOLS.some((tool) => tool.name === params.name)) return rpcError(id, RPC.INVALID_PARAMS, `Unknown tool: ${params.name}`);
      const outcome = runTool(knowledge, params.name, params.arguments ?? {}, { base: siteUrl });
      return result({ content: [{ type: 'text', text: outcome.text }], isError: outcome.isError });
    }
    default:
      return rpcError(id, RPC.METHOD_NOT_FOUND, `Method not found: ${method}`);
  }
}
