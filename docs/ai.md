# AI assistant and agents

> **Status:** the assistant answers from this documentation (English and German) through Cortex Keyring; the same knowledge is open to coding agents through an MCP server, an Agent Skill and `llms.txt`. Answers are generated: check figures against the linked page before you cut, crimp or power anything.

## Ask the assistant

The bar at the bottom of every page is the assistant.

| Do | How |
|---|---|
| Open it | Click the bar or press `/` anywhere outside a text field (`Ctrl K` / `⌘ K` stays the page search) |
| Ask | Type and press `Enter` (`Shift Enter` for a new line); it knows which page you are on |
| Show it something | Paste a screenshot or photo (`Ctrl V` / `⌘ V`), drop images or text files onto the page, or use the paperclip; a long pasted text becomes an attachment |
| Keep it open | Pin it: it becomes a sidebar on the right while you read; unpin to float it again |
| Shrink it | `Esc` or the collapse button reduces it to the small bar |
| Conversations | Click the title for your history: start a new one (`Alt N`), switch, rename or delete |
| Stop | The stop button ends an answer; the part already written is kept |

It searches the documentation, reads the pages it needs and links them in its answer; on the German site it answers in German. Photos of your build are welcome: it compares them with the assembly steps and the wiring list.

**Your data:** conversations and attachments are stored by the assistant service for your account only, until you delete them. **Availability:** the assistant runs on the owner's Cortex Keyring subscription; when the bar shows a lock, it is not available for your account.

## Use the knowledge base in your own agent

The documentation is published for language models and coding agents in three forms.

### MCP server

The MCP server is `https://strido.cortex.a2olabs.com/mcp`. Agents sign in with a personal Cortex app token (90 days by default):

```sh
cortex --json api post /api/v1/apps/strido/tokens --data '{"label":"my agent"}'   # prints {"id", "token": "cxu_...", "expiresAt"}
export STRIDO_TOKEN=cxu_...                                                         # keep it out of files you share
claude mcp add --transport http strido https://strido.cortex.a2olabs.com/mcp --header "Authorization: Bearer $STRIDO_TOKEN"
```

Codex: add `[mcp_servers.strido]` with `url = "https://strido.cortex.a2olabs.com/mcp"` and `bearer_token_env_var = "STRIDO_TOKEN"` to `~/.codex/config.toml`. Tools:

| Tool | Returns |
|---|---|
| `search_docs` | the best-matching sections (title, link, snippet), English or German |
| `read_page` | a whole page or one section as Markdown |
| `list_pages` | the site map with links |
| `search_parts` | bill-of-materials lines with quantity, price, shop and product data |

`cortex api delete /api/v1/apps/strido/tokens/<id>` revokes the token.

### Agent Skill with the full documentation

[Download the skill (ZIP)](/downloads/strido-skill.zip) (or, with the token: `curl -H "Authorization: Bearer $STRIDO_TOKEN" -o strido-skill.zip https://strido.cortex.a2olabs.com/api/agent/strido-skill.zip`) and unpack it into your agent's skill directory (Claude Code: `~/.claude/skills/`, Codex: `~/.agents/skills/`). It holds `strido/SKILL.md` and every page in English and German under `references/`, so an agent can answer offline; fetch it again after a release.

### llms.txt

| File | Contents |
|---|---|
| [/llms.txt](/llms.txt) | index of every page with its link ([German](/de/llms.txt)) |
| [/llms-full.txt](/llms-full.txt) | every page in one Markdown file ([German](/de/llms-full.txt)) |

The site needs a Cortex sign-in: people download the files in the browser; agents use the MCP server or fetch the same files with the app token under `/api/agent/` (`llms.txt`, `llms-full.txt`, `de/llms.txt`, `de/llms-full.txt`).
