# Strido documentation site and its assistant, from one build of the site content.
# Build context: the repository root (docker-compose.docs.yml); file list in Dockerfile.dockerignore.
#   target docs       VitePress build served by nginx on 8080 with /healthz
#   target assistant  assistant service (AI bar API, MCP, agent files) on 8090, knowledge = the synced pages
FROM node:26.1.0-alpine AS build
WORKDIR /repo/docs-site
COPY docs-site/package.json docs-site/package-lock.json ./
RUN npm ci --no-audit --no-fund
WORKDIR /repo
# Canonical sources the sync step publishes: Markdown, German translation catalogues, renders, viewer
# model, catalogue PDF, print kit (STLs, plates, profile, print list), the agent skill.
COPY README.md CHANGELOG.md ./
COPY docs ./docs
COPY requirements ./requirements
COPY hardware/print ./hardware/print
COPY i18n ./i18n
COPY skills ./skills
COPY docs-site/scripts ./docs-site/scripts
COPY docs-site/content ./docs-site/content
RUN cd docs-site && npm run build

FROM node:26.1.0-alpine AS assistant
WORKDIR /app
COPY assistant/package.json ./
COPY assistant/src ./src
# Knowledge: the published pages (English and German), the sidebar and the runtime data and agent files.
COPY --from=build /repo/docs-site/content/docs /knowledge/docs
COPY --from=build /repo/docs-site/content/requirements /knowledge/requirements
COPY --from=build /repo/docs-site/content/de /knowledge/de
COPY --from=build /repo/docs-site/content/.vitepress/generated.json /knowledge/.vitepress/generated.json
COPY --from=build /repo/docs-site/content/public/bom /knowledge/public/bom
COPY --from=build /repo/docs-site/content/public/catalog/parts.json /repo/docs-site/content/public/catalog/parts.de.json /knowledge/public/catalog/
COPY --from=build /repo/docs-site/content/public/llms.txt /repo/docs-site/content/public/llms-full.txt /knowledge/public/
COPY --from=build /repo/docs-site/content/public/de/llms.txt /repo/docs-site/content/public/de/llms-full.txt /knowledge/public/de/
COPY --from=build /repo/docs-site/content/public/downloads/strido-skill.zip /knowledge/public/downloads/
ENV NODE_ENV=production KNOWLEDGE_DIR=/knowledge ASSISTANT_DATA_DIR=/data PORT=8090
# The conversations volume takes this directory's owner when Docker creates it.
RUN mkdir /data && chown node:node /data
USER node
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8090/api/health || exit 1
CMD ["node", "src/server.mjs"]

FROM nginx:1.29-alpine AS docs
COPY docs-site/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/docs-site/content/.vitepress/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
