-- =====================================================================
-- Hangpost canonical schema (reference)
-- =====================================================================
-- This file is the human-readable source of truth for the database
-- shape. The authoritative, runnable definition is the Alembic migration
-- at apps/api/alembic/versions/0001_initial_schema.py, which executes the
-- equivalent DDL. Keep the two in sync by hand — autogenerate does not
-- round-trip PostGIS geography, pgvector, or HNSW indexes cleanly. See
-- docs/adrs/0003-handwritten-spatial-vector-migrations.md.
-- =====================================================================

-- ---------- extensions ----------
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive email/handle
CREATE EXTENSION IF NOT EXISTS postgis;    -- geography(POINT, 4326)
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector embeddings

-- ---------- enums ----------
CREATE TYPE post_type        AS ENUM ('hangout', 'local_info');
CREATE TYPE post_visibility  AS ENUM ('matched_only', 'friends_of_friends', 'public_in_area');
CREATE TYPE hangout_status   AS ENUM ('open', 'closed', 'cancelled');
CREATE TYPE rsvp_status      AS ENUM ('interested', 'going', 'cancelled');
CREATE TYPE friendship_state AS ENUM ('pending', 'accepted', 'blocked');
CREATE TYPE report_status    AS ENUM ('open', 'triaging', 'actioned', 'dismissed');
CREATE TYPE notif_kind       AS ENUM ('new_match', 'hangout_invite', 'rsvp', 'comment', 'friend_request');

-- ---------- core identity ----------
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_provider TEXT NOT NULL,
    auth_sub      TEXT NOT NULL,
    email         CITEXT UNIQUE NOT NULL,
    phone         TEXT UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ,
    UNIQUE (auth_provider, auth_sub)
);

-- ---------- profile (mirrors hangpost_matching.UserProfile + product fields) ----------
CREATE TABLE profiles (
    user_id           UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name      TEXT NOT NULL,
    handle            CITEXT UNIQUE NOT NULL,
    avatar_url        TEXT,
    age               SMALLINT CHECK (age BETWEEN 13 AND 120),
    hometown          TEXT,
    college           TEXT,
    interests         TEXT[] NOT NULL DEFAULT '{}',
    liked_topics      TEXT[] NOT NULL DEFAULT '{}',
    bio_synthesized   TEXT,
    embedding         vector(384),
    embedding_at      TIMESTAMPTZ,
    onboarded_at      TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX profiles_interests_gin  ON profiles USING gin (interests);
CREATE INDEX profiles_liked_gin      ON profiles USING gin (liked_topics);
CREATE INDEX profiles_hometown       ON profiles (lower(hometown));
CREATE INDEX profiles_college        ON profiles (lower(college));
CREATE INDEX profiles_embedding_hnsw ON profiles USING hnsw (embedding vector_cosine_ops);

-- ---------- current location (the RADIUS pre-filter source of truth) ----------
CREATE TABLE user_locations (
    user_id      UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    geom         geography(POINT, 4326) NOT NULL,
    accuracy_m   INTEGER,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX user_locations_gist ON user_locations USING gist (geom);
-- Radius candidate retrieval (upstream of the matching engine):
--   SELECT user_id FROM user_locations
--   WHERE ST_DWithin(geom, ST_MakePoint(:lon,:lat)::geography, :radius_m);

-- ---------- friend graph ----------
CREATE TABLE friendships (
    requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    addressee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state        friendship_state NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (requester_id, addressee_id),
    CHECK (requester_id <> addressee_id)
);
CREATE INDEX friendships_addressee ON friendships (addressee_id, state);

CREATE TABLE friendship_imports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source          TEXT NOT NULL,
    imported_count  INTEGER NOT NULL,
    consent_hash    TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- posts (city posterboard content) ----------
CREATE TABLE posts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type          post_type NOT NULL,
    visibility    post_visibility NOT NULL,
    body          TEXT NOT NULL,
    posted_geom   geography(POINT, 4326) NOT NULL,
    radius_m      INTEGER NOT NULL DEFAULT 5000,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ
);
CREATE INDEX posts_geom_gist ON posts USING gist (posted_geom);
CREATE INDEX posts_created   ON posts (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX posts_author    ON posts (author_id, created_at DESC);

CREATE TABLE post_media (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id    UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    r2_key     TEXT NOT NULL,
    mime       TEXT NOT NULL,
    width      INTEGER,
    height     INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0
);

-- ---------- hangouts (1:1 with posts where type='hangout') ----------
CREATE TABLE hangouts (
    post_id      UUID PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
    starts_at    TIMESTAMPTZ NOT NULL,
    ends_at      TIMESTAMPTZ,
    venue        TEXT,
    max_rsvps    INTEGER,
    status       hangout_status NOT NULL DEFAULT 'open'
);

CREATE TABLE hangout_rsvps (
    hangout_id  UUID NOT NULL REFERENCES hangouts(post_id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status      rsvp_status NOT NULL,
    rsvped_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (hangout_id, user_id)
);
CREATE INDEX hangout_rsvps_user ON hangout_rsvps (user_id, rsvped_at DESC);

-- ---------- THE ML LOOP — recommendation outcome logs ----------
CREATE TABLE recommendation_impressions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    candidate_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    surfaced_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    rank_position   SMALLINT NOT NULL,
    score           REAL NOT NULL,
    model_version   TEXT NOT NULL,
    breakdown_json  JSONB NOT NULL
);
CREATE INDEX rec_imp_source ON recommendation_impressions (source_user_id, surfaced_at DESC);

CREATE TABLE recommendation_outcomes (
    impression_id       UUID PRIMARY KEY REFERENCES recommendation_impressions(id) ON DELETE CASCADE,
    viewed_at           TIMESTAMPTZ,
    profile_opened      BOOLEAN NOT NULL DEFAULT false,
    friend_request_sent BOOLEAN NOT NULL DEFAULT false,
    blocked             BOOLEAN NOT NULL DEFAULT false,
    hangout_rsvped      BOOLEAN NOT NULL DEFAULT false,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- safety ----------
CREATE TABLE user_blocks (
    blocker_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (blocker_id, blocked_id),
    CHECK (blocker_id <> blocked_id)
);

CREATE TABLE reports (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_id    UUID NOT NULL REFERENCES users(id),
    target_user_id UUID REFERENCES users(id),
    target_post_id UUID REFERENCES posts(id),
    reason         TEXT NOT NULL,
    detail         TEXT,
    status         report_status NOT NULL DEFAULT 'open',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at    TIMESTAMPTZ,
    CHECK (target_user_id IS NOT NULL OR target_post_id IS NOT NULL)
);

-- ---------- notifications ----------
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind        notif_kind NOT NULL,
    payload     JSONB NOT NULL,
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE read_at IS NULL;
