# Local dev database: PostGIS image plus pgvector. No single official image
# ships both, so we layer the PGDG pgvector package onto the PostGIS image.
FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
