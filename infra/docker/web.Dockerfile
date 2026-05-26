# Build context is the repo root (see infra/compose/docker-compose.yml).
# Next.js standalone output keeps the runtime image small.

FROM node:22-slim AS builder
WORKDIR /app/apps/web

ENV NEXT_TELEMETRY_DISABLED=1

COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install

COPY apps/web ./
RUN npm run build

# ---- runtime ----
FROM node:22-slim AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

# Standalone bundle (requires output: "standalone" once enabled in next.config).
COPY --from=builder /app/apps/web/public ./public
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./.next/static

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 3000
CMD ["node", "apps/web/server.js"]
