# **Hangpost — Full-Stack Build Plan**

## 0\. Executive summary

You're building a mobile-first, location-scoped social network where the matching engine you already shipped becomes one bounded service in a larger system. The architectural goal is "modular monolith that could split into microservices if traffic justifies it" — not microservices on day one, because day-one microservices for a solo dev is a red flag, not a senior signal. Senior engineers know when to NOT distribute.  
The headline tech choices (rationale follows in §3):

* Modular monolith — single deployable, internal domain boundaries enforced by Python packages.  
* Python FastAPI backend → reuses the matching engine without IPC.  
* Next.js 15 \+ React 19 \+ TypeScript \+ Tailwind v4 \+ shadcn/ui frontend → industry standard, ships PWA out of the box.  
* PostgreSQL 16 with PostGIS \+ pgvector → the radius pre-filter is literally a ST\_DWithin query; profile embeddings are first-class.  
* Redis → sessions, rate limits, WebSocket pub/sub, hot recommendation cache.  
* Docker \+ docker-compose for local dev; Fly.io or Railway for production hosting; Vercel for the frontend.  
* GitHub Actions for CI/CD with PR preview environments.  
* OpenTelemetry \+ Sentry \+ structured JSON logs for observability from day one.  
* Clerk for auth (or self-hosted Supabase Auth if you want the "I built it" signal).

The resume story this tells: *"I designed and shipped a real social-media product with a recommendation engine I built, evaluated, and distilled myself. The data model, services, deployment, and CI/CD are production-grade. I closed the ML loop by feeding live outcome data back into the ranker."* That's a senior-engineer pitch.  
---

## 1\. Repo strategy

Two repos. Keep them separate forever.  
hangpost-matching-engine/     ← what you have now. Stays focused.  
   (PyPI package: hangpost-matching)  
   └── publishes to PyPI on tagged release  
hangpost-app/                 ← new repo. Full-stack app.  
   apps/  
       api/                  ← FastAPI service  
       web/                  ← Next.js frontend  
   packages/  
       shared-types/         ← OpenAPI-generated TS client \+ schema  
   infra/  
       docker/               ← Dockerfiles  
       compose/              ← docker-compose for local dev  
       k8s/                  ← Optional: Helm charts for later  
       terraform/            ← Optional: infrastructure-as-code  
   docs/  
       adrs/                 ← Architecture Decision Records  
       ARCHITECTURE.md  
       RUNBOOK.md  
   .github/  
       workflows/  
The app repo pip installs hangpost-matching as a dependency. If you publish the matching engine to PyPI (cheap and easy), it's pip install hangpost-matching. If not, it's pip install hangpost-matching @ git+https://github.com/....  
Why a monorepo *within* the app repo, not separate api / web repos?

* One PR can change both API and web (typed-client regeneration).  
* One CI run, one release cadence, one issue tracker.  
* pnpm workspaces or just plain folders — no heavy tooling like Nx/Turborepo needed at this scale.

---

## 2\. Architecture diagram

┌─────────────────────────────────────────────────────────────────────┐  
│                         Public internet                              │  
└──────────────────────────────┬──────────────────────────────────────┘  
                              │  
                 ┌────────────┴────────────┐  
                 │                         │  
           ┌─────▼─────┐             ┌─────▼─────┐  
           │  Vercel   │             │ Cloudflare│  
           │ (Next.js) │             │  (DNS+CDN)│  
           └─────┬─────┘             └───────────┘  
                 │  
                 │  HTTPS, JWT in httpOnly cookie  
                 │  
           ┌─────▼──────────────────────────┐  
           │   FastAPI app (Fly.io / Railway) │  
           │                                  │  
           │   ┌────────────────────────┐     │  
           │   │ Auth (Clerk webhook    │     │  
           │   │  / Supabase Auth)      │     │  
           │   ├────────────────────────┤     │  
           │   │ Profiles, Posts,       │     │  
           │   │ Hangouts, Friends,     │     │  
           │   │ Notifications, Reports │     │  
           │   ├────────────────────────┤     │  
           │   │ Matching service       │     │  
           │   │ (imports hangpost-     │     │  
           │   │  matching package)     │     │  
           │   └────────────────────────┘     │  
           └──┬───────────┬──────────────┬────┘  
              │           │              │  
       ┌──────▼──┐  ┌─────▼─────┐  ┌─────▼──────┐  
       │Postgres │  │   Redis   │  │     S3     │  
       │+PostGIS │  │ sess/rate │  │   /R2      │  
       │+pgvector│  │ pub/sub   │  │  (photos)  │  
       │(Neon/   │  │           │  │            │  
       │Supabase)│  │           │  │            │  
       └─────────┘  └───────────┘  └────────────┘  
       ┌──────────────────────────────────┐  
       │  Async workers (Arq / Celery)    │  
       │  \- Embed new profiles            │  
       │  \- Send notifications            │  
       │  \- Batch recompute recs          │  
       │  \- Periodic re-train ML model    │  
       └──────────────────────────────────┘  
       ┌──────────────────────────────────┐  
       │  Observability sidecar            │  
       │  \- OTel collector                │  
       │  \- Sentry SDK                    │  
       │  \- Structured logs to Grafana    │  
       └──────────────────────────────────┘  
---

## 3\. Tech stack matrix with rationale

| Layer | Choice | Why this one | Why not the obvious alternative |
| :---- | :---- | :---- | :---- |
| Frontend framework | Next.js 15 App Router | Server components, streaming SSR, mature ecosystem, Vercel hosting is free-tier-friendly | SvelteKit is nicer DX but smaller talent pool; Remix folded into RR7 |
| Frontend language | TypeScript | Mandatory for senior signal in 2026 | — |
| Styling | Tailwind v4 \+ shadcn/ui | Fast, looks great, accessible by default, AI-friendly | CSS modules are fine but slower to ship; MUI is heavy |
| State (server) | TanStack Query | Industry standard, mature | SWR is fine but smaller mindshare |
| State (client) | Zustand | Tiny, no boilerplate | Redux Toolkit is the "safe" choice but overkill here |
| Forms | react-hook-form \+ zod | The combination is the de facto standard | Formik is legacy |
| Backend framework | FastAPI | Async, Pydantic v2, auto OpenAPI, reuses matching engine in-process | Node+Hono is great but you'd lose direct Python ML integration |
| ORM | SQLAlchemy 2.0 async | The standard. Pairs with Alembic for migrations | Tortoise/Piccolo are nice but immature; bare SQL is fine but loses migrations |
| Validation | Pydantic v2 | Built into FastAPI; insanely fast | — |
| Database | PostgreSQL 16 | The senior default. JSONB, full-text search, triggers, transactions | MongoDB is the wrong shape for a social graph |
| Geo | PostGIS | Industry standard for spatial queries. ST\_DWithin is the radius pre-filter | Manual Haversine in app code → loses GIST index, doesn't scale |
| Vectors | pgvector | Embeddings live next to the data; cosine HNSW indexes | Pinecone/Weaviate add a network hop and a vendor |
| Cache / pub-sub | Redis 7 | Sessions, rate limits, pub/sub for WebSockets, hot rec cache | KeyDB if you want a fork; Valkey if you want the new fork |
| Auth | Clerk (free tier) | Looks production-grade, ships in an hour, free up to 10K MAU | Roll-your-own is a CV trap; Supabase Auth is the self-hosted "I get it" alt |
| Background jobs | Arq | Async-native, Redis-backed, tiny | Celery is the textbook answer but heavier |
| Real-time | FastAPI WebSockets \+ Redis pub/sub | Native, simple, scales horizontally because Redis is the bus | Pusher/Ably are fine but vendor lock-in |
| Object storage | Cloudflare R2 | S3-compatible API, \~10× cheaper egress than S3 | S3 if you want the textbook answer |
| Image transforms | Cloudflare Images or imgix | On-demand resize \+ format negotiation | DIY with Sharp at the edge is feasible but more code |
| Email | Resend | Best DX, generous free tier, React Email for templates | Postmark / SendGrid are fine but uglier APIs |
| Push notifications | Web Push Protocol (browser-native) \+ Expo Notifications (if you add RN later) | Standards-based, free | OneSignal is fine but vendor |
| Frontend hosting | Vercel | Free hobby tier, zero-config Next.js, preview deploys per PR | Netlify is fine; Cloudflare Pages is the cheapest |
| Backend hosting | Fly.io (preferred) or Railway | Postgres \+ Redis \+ your app, deployed via Dockerfile, regional. \~$5–20/mo to start | AWS is the resume default but ECS/Fargate is a lot of YAML for a solo dev |
| Managed Postgres | Neon or Supabase | Both have PostGIS \+ pgvector in their free tiers | RDS is the textbook answer but $$$ |
| CI/CD | GitHub Actions | Already on GitHub, free for public repos | CircleCI is fine; ArgoCD if you're going K8s |
| Observability | OpenTelemetry → Grafana Cloud \+ Sentry | OTel is the vendor-neutral standard; Sentry's free tier is great | Datadog is the "enterprise" answer at enterprise prices |
| Logs | Structured JSON to stdout | Captured by Fly/Railway log shipper, forwarded to Grafana Loki or Better Stack | Don't roll your own |
| E2E tests | Playwright | Cross-browser, fast, the new standard | Cypress is fine; Selenium is dead |
| Unit tests (Python) | pytest \+ pytest-asyncio | Already what you use | — |
| Unit tests (TS) | Vitest | Faster than Jest, same API | — |
| Component testing | Storybook \+ Chromatic | Visual regression for free \+ design system docs | Optional but huge senior signal |
| Linting (Python) | ruff \+ mypy | Already standard | — |
| Linting (TS) | eslint \+ prettier \+ tsc \--noEmit | Standard | Biome is the new hotness but ecosystem isn't there |
| Containers | Docker, multi-stage, distroless | Tiny images, fast cold starts | — |
| Dev environment | Codespaces with devcontainer.json | Matches your browser-only workflow | — |

---

## 4\. Domain model \+ database schema

This is the architecturally interesting part. Get this right and everything else is filling in code.  
*\-- \=====================================================*  
*\-- enums*  
*\-- \=====================================================*  
CREATE TYPE post\_type        AS ENUM ('hangout', 'local\_info');  
CREATE TYPE post\_visibility  AS ENUM ('matched\_only', 'friends\_of\_friends', 'public\_in\_area');  
CREATE TYPE hangout\_status   AS ENUM ('open', 'closed', 'cancelled');  
CREATE TYPE rsvp\_status      AS ENUM ('interested', 'going', 'cancelled');  
CREATE TYPE friendship\_state AS ENUM ('pending', 'accepted', 'blocked');  
CREATE TYPE report\_status    AS ENUM ('open', 'triaging', 'actioned', 'dismissed');  
CREATE TYPE notif\_kind       AS ENUM ('new\_match', 'hangout\_invite', 'rsvp', 'comment', 'friend\_request');

*\-- \=====================================================*  
*\-- core identity*  
*\-- \=====================================================*  
CREATE TABLE users (  
   id            UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
   auth\_provider TEXT NOT NULL,             *\-- 'clerk' | 'apple' | 'google' | etc.*  
   auth\_sub      TEXT NOT NULL,             *\-- provider's stable user id*  
   email         CITEXT UNIQUE NOT NULL,  
   phone         TEXT UNIQUE,  
   created\_at    TIMESTAMPTZ NOT NULL DEFAULT now(),  
   deleted\_at    TIMESTAMPTZ,               *\-- soft delete (GDPR-friendly)*  
   UNIQUE (auth\_provider, auth\_sub)  
);

*\-- \=====================================================*  
*\-- profile (mirrors hangpost\_matching.UserProfile \+ product fields)*  
*\-- \=====================================================*  
CREATE TABLE profiles (  
   user\_id           UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,  
   display\_name      TEXT NOT NULL,  
   handle            CITEXT UNIQUE NOT NULL,  
   avatar\_url        TEXT,  
   age               SMALLINT CHECK (age BETWEEN 13 AND 120),  
   hometown          TEXT,  
   college           TEXT,  
   interests         TEXT\[\] NOT NULL DEFAULT '{}',  
   liked\_topics      TEXT\[\] NOT NULL DEFAULT '{}',  
   bio\_synthesized   TEXT,                  *\-- output of profile\_to\_text(), regenerated on profile update*  
   embedding         vector(384),           *\-- pgvector: sentence-transformers MiniLM*  
   embedding\_at      TIMESTAMPTZ,  
   onboarded\_at      TIMESTAMPTZ,  
   updated\_at        TIMESTAMPTZ NOT NULL DEFAULT now()  
);  
CREATE INDEX profiles\_interests\_gin    ON profiles USING gin (interests);  
CREATE INDEX profiles\_liked\_gin        ON profiles USING gin (liked\_topics);  
CREATE INDEX profiles\_hometown         ON profiles (lower(hometown));  
CREATE INDEX profiles\_college          ON profiles (lower(college));  
CREATE INDEX profiles\_embedding\_hnsw   ON profiles USING hnsw (embedding vector\_cosine\_ops);

*\-- \=====================================================*  
*\-- current location (the RADIUS pre-filter source of truth)*  
*\-- \=====================================================*  
CREATE TABLE user\_locations (  
   user\_id      UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,  
   geom         geography(POINT, 4326) NOT NULL,   *\-- PostGIS, geodesic*  
   accuracy\_m   INTEGER,  
   updated\_at   TIMESTAMPTZ NOT NULL DEFAULT now()  
);  
CREATE INDEX user\_locations\_gist ON user\_locations USING gist (geom);  
*\-- Radius candidate retrieval (the upstream of the matching engine):*  
*\--   SELECT user\_id FROM user\_locations*  
*\--   WHERE ST\_DWithin(geom, ST\_MakePoint(:lon,:lat)::geography, :radius\_m);*

*\-- \=====================================================*  
*\-- friend graph*  
*\-- \=====================================================*  
CREATE TABLE friendships (  
   requester\_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   addressee\_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   state        friendship\_state NOT NULL,  
   created\_at   TIMESTAMPTZ NOT NULL DEFAULT now(),  
   updated\_at   TIMESTAMPTZ NOT NULL DEFAULT now(),  
   PRIMARY KEY (requester\_id, addressee\_id),  
   CHECK (requester\_id \<\> addressee\_id)  
);  
CREATE INDEX friendships\_addressee ON friendships (addressee\_id, state);

*\-- Provenance for imported friend edges (contacts, Instagram import).*  
*\-- Senior signal: never lose track of where data came from for privacy/GDPR.*  
CREATE TABLE friendship\_imports (  
   id              UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
   user\_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   source          TEXT NOT NULL,                 *\-- 'contacts' | 'instagram' | etc.*  
   imported\_count  INTEGER NOT NULL,  
   consent\_hash    TEXT NOT NULL,                 *\-- proof of consent flow*  
   created\_at      TIMESTAMPTZ NOT NULL DEFAULT now()  
);

*\-- \=====================================================*  
*\-- posts (city posterboard content)*  
*\-- \=====================================================*  
CREATE TABLE posts (  
   id            UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
   author\_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   type          post\_type NOT NULL,  
   visibility    post\_visibility NOT NULL,  
   body          TEXT NOT NULL,  
   posted\_geom   geography(POINT, 4326) NOT NULL,  
   radius\_m      INTEGER NOT NULL DEFAULT 5000,  
   created\_at    TIMESTAMPTZ NOT NULL DEFAULT now(),  
   deleted\_at    TIMESTAMPTZ  
);  
CREATE INDEX posts\_geom\_gist  ON posts USING gist (posted\_geom);  
CREATE INDEX posts\_created    ON posts (created\_at DESC) WHERE deleted\_at IS NULL;  
CREATE INDEX posts\_author     ON posts (author\_id, created\_at DESC);

CREATE TABLE post\_media (  
   id       UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
   post\_id  UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,  
   r2\_key   TEXT NOT NULL,                  *\-- key in Cloudflare R2*  
   mime     TEXT NOT NULL,  
   width    INTEGER,  
   height   INTEGER,  
   sort\_order INTEGER NOT NULL DEFAULT 0  
);

*\-- \=====================================================*  
*\-- hangouts (one-to-many with posts where post.type='hangout')*  
*\-- \=====================================================*  
CREATE TABLE hangouts (  
   post\_id      UUID PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,  
   starts\_at    TIMESTAMPTZ NOT NULL,  
   ends\_at      TIMESTAMPTZ,  
   venue        TEXT,  
   max\_rsvps    INTEGER,  
   status       hangout\_status NOT NULL DEFAULT 'open'  
);

CREATE TABLE hangout\_rsvps (  
   hangout\_id  UUID NOT NULL REFERENCES hangouts(post\_id) ON DELETE CASCADE,  
   user\_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   status      rsvp\_status NOT NULL,  
   rsvped\_at   TIMESTAMPTZ NOT NULL DEFAULT now(),  
   PRIMARY KEY (hangout\_id, user\_id)  
);  
CREATE INDEX hangout\_rsvps\_user ON hangout\_rsvps (user\_id, rsvped\_at DESC);

*\-- \=====================================================*  
*\-- THE ML LOOP — recommendation outcome logs*  
*\-- This is the table that converts your matching engine from*  
*\-- "evaluated on synthetic labels" to "evaluated on real outcomes."*  
*\-- Every (source, candidate) ever surfaced \+ every downstream action*  
*\-- becomes Phase 3 training data.*  
*\-- \=====================================================*  
CREATE TABLE recommendation\_impressions (  
   id              UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
   source\_user\_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   candidate\_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   surfaced\_at     TIMESTAMPTZ NOT NULL DEFAULT now(),  
   rank\_position   SMALLINT NOT NULL,            *\-- where in the list it appeared*  
   score           REAL NOT NULL,                *\-- ranker score*  
   model\_version   TEXT NOT NULL,                *\-- 'rules-v1' | 'learned-v3' | etc.*  
   breakdown\_json  JSONB NOT NULL                *\-- the full MatchBreakdown*  
);  
CREATE INDEX rec\_imp\_source     ON recommendation\_impressions (source\_user\_id, surfaced\_at DESC);

CREATE TABLE recommendation\_outcomes (  
   impression\_id   UUID PRIMARY KEY REFERENCES recommendation\_impressions(id) ON DELETE CASCADE,  
   viewed\_at       TIMESTAMPTZ,  
   profile\_opened  BOOLEAN NOT NULL DEFAULT false,  
   friend\_request\_sent BOOLEAN NOT NULL DEFAULT false,  
   blocked         BOOLEAN NOT NULL DEFAULT false,  
   hangout\_rsvped  BOOLEAN NOT NULL DEFAULT false,  
   updated\_at      TIMESTAMPTZ NOT NULL DEFAULT now()  
);

*\-- \=====================================================*  
*\-- safety*  
*\-- \=====================================================*  
CREATE TABLE user\_blocks (  
   blocker\_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   blocked\_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   created\_at  TIMESTAMPTZ NOT NULL DEFAULT now(),  
   PRIMARY KEY (blocker\_id, blocked\_id),  
   CHECK (blocker\_id \<\> blocked\_id)  
);

CREATE TABLE reports (  
   id         UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
   reporter\_id UUID NOT NULL REFERENCES users(id),  
   target\_user\_id UUID REFERENCES users(id),  
   target\_post\_id UUID REFERENCES posts(id),  
   reason     TEXT NOT NULL,  
   detail     TEXT,  
   status     report\_status NOT NULL DEFAULT 'open',  
   created\_at TIMESTAMPTZ NOT NULL DEFAULT now(),  
   resolved\_at TIMESTAMPTZ,  
   CHECK (target\_user\_id IS NOT NULL OR target\_post\_id IS NOT NULL)  
);

*\-- \=====================================================*  
*\-- notifications*  
*\-- \=====================================================*  
CREATE TABLE notifications (  
   id          UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
   user\_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  
   kind        notif\_kind NOT NULL,  
   payload     JSONB NOT NULL,  
   read\_at     TIMESTAMPTZ,  
   created\_at  TIMESTAMPTZ NOT NULL DEFAULT now()  
);  
CREATE INDEX notifications\_user\_unread  
   ON notifications (user\_id, created\_at DESC)  
   WHERE read\_at IS NULL;  
Three callouts senior reviewers will look for:

1. recommendation\_impressions \+ recommendation\_outcomes is how the live app closes the ML loop. Every impression logs the ranker version and the full breakdown. Every downstream action (profile open, friend request, RSVP, block) lands in recommendation\_outcomes keyed by the impression. The training pipeline reads from this and replaces the synthetic labels you used in the matching-engine repo. This is your "I shipped real-world ML" story.  
2. friendship\_imports.consent\_hash captures GDPR-grade provenance for any imported edge.  
3. PostGIS geography (not geometry) because we want geodesic distance from day one — no flat-earth math when you go international.

---

## 5\. Phased build plan (10–14 weeks, \~10 hrs/week)

Each phase ends in a deployable, demoable increment. Don't skip the demo step — momentum matters.

| Phase | Weeks | Outcome | Resume signal |
| :---- | :---- | :---- | :---- |
| 0\. Foundation | 1–2 | New repo, devcontainer, docker-compose with Postgres+Redis+API+Web, Alembic migrations for the schema above, CI skeleton (lint+test+build), one ADR per major decision | "I scaffolded a production-grade monorepo with CI from day one." |
| 1\. Auth \+ Profile | 1–2 | Clerk integrated, profile creation/edit, profile\_to\_text regeneration on save, embedding write to pgvector | "Clerk auth, type-safe API client generated from OpenAPI." |
| 2\. Location \+ Feed MVP | 1–2 | PWA geolocation capture, PostGIS radius query, posterboard feed UI, post creation | "PostGIS radius pre-filter; geo-indexed feed query in \<50ms p95." |
| 3\. Matching integration | 1 | /recommendations endpoint that imports hangpost\_matching, returns top-K with MatchBreakdown JSON, frontend explanation card UI, impression logging | "The matching engine I built in repo 1 is shipped here as a service. Every impression is logged with the full explainable breakdown." |
| 4\. Hangouts \+ Real-time | 1–2 | Hangout post type, RSVP flow, WebSocket notifications via Redis pub/sub | "FastAPI WebSockets backed by Redis pub/sub for horizontal scale." |
| 5\. Friend graph \+ Social | 1–2 | Friend requests, contact import flow (with consent capture), blocks, reports | "First-class safety primitives, GDPR-grade consent provenance." |
| 6\. Observability \+ hardening | 1–2 | OTel traces, Sentry, structured JSON logs, rate limiting, CSP, security headers, load test with k6 | "p95 \< 200ms under 100 RPS in load tests, traced end-to-end." |
| 7\. Close the ML loop | 1 | Outcome instrumentation, daily ETL of recommendation\_outcomes → training set, weekly LightGBM retrain via Arq scheduler, model registry in S3, A/B harness | "Shipped a continuous training loop: live outcomes → fresh model weekly, A/B-tested against the current champion." |

---

## 6\. CI/CD pipeline design

Three pipelines:  
PR pipeline (every commit on every PR):

1. Lint: ruff \+ mypy \+ eslint \+ tsc  
2. Test: pytest \+ vitest (unit \+ integration)  
3. Build: Docker image for api, Next.js build for web  
4. Security scan: trivy fs . \+ pip-audit \+ npm audit (or just rely on Dependabot)  
5. Deploy a preview environment: spin up the docker-compose stack on a Fly.io app named pr-\<number\>-hangpost, comment the URL on the PR. This is the "wow" feature.  
6. Run Playwright E2E against the preview URL (smoke suite, \~5 critical journeys).

Main pipeline (push to main):

1. Everything above.  
2. Deploy to staging automatically.  
3. Run full E2E suite against staging.  
4. Manual approval gate.  
5. Deploy to production (blue/green via Fly's fly deploy \--strategy bluegreen).  
6. Post-deploy: run smoke tests, ping Sentry release endpoint, post to Slack.

Nightly pipeline:

1. Re-train LightGBM ranker on last 7 days of recommendation\_outcomes.  
2. Run offline evaluation harness (same one in the matching-engine repo).  
3. If new model beats champion by \>2% NDCG, open a PR with the new model artifact registered.

This trio is the senior-CV trifecta: PR previews \+ blue/green prod \+ scheduled ML retraining.  
---

## 7\. Deployment topology

For \~$25/month you can run something genuinely production-grade:

* Vercel (frontend) — free hobby tier covers \~100GB bandwidth/mo  
* Fly.io (API \+ workers) — fly machines × 2 (HA pair), shared CPU 1x with 512MB → \~$5/mo  
* Neon (Postgres) — free tier handles 0.5GB storage, \~190 hours of compute → free  
* Upstash (Redis) — free tier 10K commands/day, paid plan \~$10/mo as you grow  
* Cloudflare R2 — first 10GB free; \~$0.015/GB after  
* Sentry — free tier covers 5K events/mo  
* Grafana Cloud — free tier covers 50GB logs, 14d retention

Scale up by upgrading individual services. The architecture doesn't change.  
---

## 8\. Observability \+ security baselines

Observability — do this in Phase 0, not later. The cost of adding traces after the app is built is 10× the cost of adding them from the start.

* Every request gets a X-Request-ID header (generate if absent).  
* Every log line is structured JSON with request\_id, user\_id, path, latency\_ms, status.  
* Every endpoint emits an OTel span; spans propagate through DB calls (SQLAlchemy instrumentation) and to the matching engine (manual @trace decorator on rank\_candidates).  
* Sentry SDK installed in both FastAPI and Next.js; release version pinned to the git SHA.  
* One golden dashboard in Grafana: requests/sec, p50/p95/p99 latency by endpoint, error rate by endpoint, DB connection pool usage, Redis ops/sec.  
* One SLO: 99.5% of recommendation requests under 200ms.

Security baselines:

* HTTPS-only, HSTS, Secure \+ SameSite=Lax cookies.  
* CSP with nonces (Next.js makes this easy).  
* Rate limiting: 60 req/min per IP and 600 req/min per authenticated user, Redis-backed via slowapi.  
* Argon2 password hashing if you self-host auth (Clerk handles this for you).  
* All inputs validated through Pydantic models; never \*\*request.json() straight into the DB.  
* Parameterized SQL only (SQLAlchemy default).  
* Secrets only in env vars; rotate quarterly; never logged.  
* Dependabot \+ CodeQL enabled at repo creation time.  
* Bug bounty in your README's SECURITY.md (just a contact email is fine).

---

## 9\. Closing the ML loop (the killer feature)

Diagram this as one slide on your resume:  
┌──────────┐    rank()    ┌──────────────┐  impression  ┌─────────────────┐  
│ FastAPI  │─────────────▶│ hangpost-    │─────────────▶│ recommendation\_ │  
│  API     │              │  matching    │              │  impressions    │  
└──────────┘              │  (Phase 3\)   │              └────────┬────────┘  
    ▲                    └──────────────┘                       │  
    │                                                            │ user action  
    │                                                            ▼  
    │                                                  ┌─────────────────┐  
    │                                                  │ recommendation\_ │  
    │                                                  │  outcomes       │  
    │                                                  └────────┬────────┘  
    │                                                            │  
    │                                                            │ nightly ETL  
    │                                                            ▼  
┌────┴──────┐  hot-swap   ┌──────────────┐   train     ┌─────────────────┐  
│  Model    │◀────────────│  Arq worker  │◀────────────│ outcomes →      │  
│  registry │   if better │ \+ LightGBM   │             │ Query objects   │  
│  (S3)     │   on offline│              │             │                 │  
└───────────┘   metrics   └──────────────┘             └─────────────────┘  
The matching-engine repo's LearnedRanker.fit(queries) already accepts a Query iterable. The app's nightly ETL just produces those Query objects from the outcomes table. You don't have to change the matching engine at all — that's the whole point of the protocol-based design you already shipped. Senior reviewers will notice.  
---

## 10\. Day-1 bootstrap (Codespaces-friendly)

When you're ready to start (after the labeling job finishes and we've finalized the matching-engine repo), here's the exact sequence — all in your browser:  
Step A — Create the new repo.

1. Open [https://github.com/new](https://github.com/new).  
2. Name: hangpost-app. Private to start (flip to public when it's pretty).  
3. Initialize with README \+ MIT license \+ Python .gitignore.  
4. Create.

Step B — Open it in Codespaces.

1. Green Code button → Codespaces → Create codespace on main.  
2. In the terminal, create the monorepo skeleton (copy-paste this whole block):

*\# Folder structure*  
mkdir \-p apps/api/src/hangpost\_api apps/api/tests  
mkdir \-p apps/web/src apps/web/tests  
mkdir \-p packages/shared-types  
mkdir \-p infra/docker infra/compose  
mkdir \-p docs/adrs  
mkdir \-p .github/workflows

*\# pyproject for the API*  
cat \> apps/api/pyproject.toml \<\<'EOF'  
\[build-system\]  
requires \= \["setuptools\>=68", "wheel"\]  
build-backend \= "setuptools.build\_meta"

\[project\]  
name \= "hangpost-api"  
version \= "0.1.0"  
requires-python \= "\>=3.11"  
dependencies \= \[  
   "fastapi\[standard\]\>=0.115",  
   "uvicorn\[standard\]\>=0.32",  
   "pydantic\>=2.9",  
   "sqlalchemy\[asyncio\]\>=2.0",  
   "alembic\>=1.13",  
   "asyncpg\>=0.30",  
   "redis\>=5.0",  
   "pgvector\>=0.3",  
   "geoalchemy2\>=0.15",  
   "arq\>=0.26",  
   "structlog\>=24.4",  
   "opentelemetry-api\>=1.27",  
   "opentelemetry-sdk\>=1.27",  
   "opentelemetry-instrumentation-fastapi\>=0.48b0",  
   "sentry-sdk\[fastapi\]\>=2.18",  
   "hangpost-matching @ git+https://github.com/ai-bryguy101/hangpost-app@main",  
\]

\[project.optional-dependencies\]  
dev \= \["pytest\>=8", "pytest-asyncio\>=0.24", "httpx\>=0.28", "ruff\>=0.7", "mypy\>=1.13"\]  
EOF  
Step C — docker-compose for local dev (one file, runs everything):  
cat \> infra/compose/docker-compose.yml \<\<'EOF'  
services:  
 db:  
   image: postgis/postgis:16-3.4  
   environment:  
     POSTGRES\_USER: hangpost  
     POSTGRES\_PASSWORD: hangpost  
     POSTGRES\_DB: hangpost  
   ports: \["5432:5432"\]  
   volumes: \["pgdata:/var/lib/postgresql/data"\]  
 redis:  
   image: redis:7-alpine  
   ports: \["6379:6379"\]  
 api:  
   build:  
     context: ../..  
     dockerfile: infra/docker/api.Dockerfile  
   environment:  
     DATABASE\_URL: postgresql+asyncpg://hangpost:hangpost@db/hangpost  
     REDIS\_URL: redis://redis:6379/0  
   ports: \["8000:8000"\]  
   depends\_on: \[db, redis\]  
 web:  
   build:  
     context: ../..  
     dockerfile: infra/docker/web.Dockerfile  
   environment:  
     NEXT\_PUBLIC\_API\_URL: http://localhost:8000  
   ports: \["3000:3000"\]  
   depends\_on: \[api\]  
volumes:  
 pgdata:  
EOF  
After that, you're ready to docker compose up in Codespaces and have the whole stack running.  
Step D — The first ADR (this is the senior-signal move):  
cat \> docs/adrs/0001-modular-monolith.md \<\<'EOF'  
\# ADR 0001: Modular monolith over microservices for v1

\#\# Status  
Accepted, 2026-XX-XX.

\#\# Context  
Hangpost has multiple bounded contexts (auth, profiles, posts, hangouts,  
matching, notifications). The team is one engineer (me). Time-to-first-user  
is more important than future-team-scaling.

\#\# Decision  
Build a modular monolith in FastAPI. Each bounded context is a Python  
package under \`apps/api/src/hangpost\_api/\<domain\>/\`. Cross-domain calls  
go through service-layer functions, never through repository imports from  
other domains. The matching engine remains its own pip-installed package  
(repo: hangpost-matching-engine) so it can be deployed as a sidecar later.

\#\# Consequences  
\+ One deploy, one runbook, one log stream.  
\+ Refactoring across domains is cheap (no IPC contracts).  
\+ When a single domain needs different scaling, extracting it is a known  
 pattern: lift the package, add a thin HTTP/gRPC façade.  
\- Need discipline to enforce domain boundaries (code review, no  
 cross-domain repository imports — enforced by a custom ruff rule).  
EOF  
---

## What I'd skip (or defer) — senior judgment

* GraphQL — REST \+ OpenAPI codegen is enough and ships faster. Add GraphQL when the frontend actually has 5+ heterogeneous data needs that REST can't model well.  
* Kubernetes — Fly.io / Railway are not "less production"; they're a *deliberately simpler abstraction over the same primitives*. Add K8s only when traffic forces it.  
* Microservices — see ADR-0001 above.  
* Event sourcing / CQRS — wildly overkill for v1. Plain Postgres tables \+ audit log.  
* GraphDB (Neo4j) for the friend graph — Postgres handles it fine at this scale. Reach for Neo4j at 10M+ users.  
* Custom auth — Clerk for 0–10K MAU. Migrate to Supabase Auth or self-hosted if you need it.  
* Mobile native (RN) on day 1 — PWA \+ Next.js gets you 80% of the experience for 10% of the effort. Add RN/Expo in month 4\.  
* Service mesh (Linkerd / Istio) — see microservices.  
* AI agents / LangChain in the product — gimmicky in a social product. The matching engine is the ML differentiator; don't dilute it with chatbots.

---

## Concrete next actions (in priority order)

While you finish the matching-engine work in your current Codespace:

1. Bookmark this plan. (Maybe save it as a gist for safekeeping — copy the markdown, go to [https://gist.github.com/](https://gist.github.com/), paste, save as hangpost-architecture-plan.md.)  
2. Decide on auth: Clerk vs Supabase Auth. This is a 30-minute research read. Clerk wins on speed-to-ship; Supabase wins on "I get it" senior signal.  
3. Decide on hosting: Fly.io vs Railway. Both are great. Fly's regional / edge story is stronger; Railway's DX is friendlier.  
4. Pick a name for the new repo: hangpost-app is the obvious choice.  
5. Once the matching engine is done shipping (after the README updates land), create the new repo using §10 above.

When you're ready to actually start building, ping me in this thread and I'll generate the first round of real code — FastAPI app skeleton, Next.js app skeleton, Alembic migrations for the schema above, the docker-compose.yml in its actual final form, the first GitHub Actions workflow, and the first ADRs. We can do that in a fresh Claude Code session on the new repo so this one stays focused on the matching engine.  
Back to the matching engine — once /tmp/four\_phase\_eval.txt and /tmp/bench\_full.txt are populated, paste them here and I'll close out the README \+ benchmark work in this repo before we move on.  
