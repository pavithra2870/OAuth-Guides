-- Two tables. Run with: python backend/scripts/migrate.py  (idempotent)

-- One row per app. This table is both the library and the cache:
-- curated guides and live-generated guides live side by side.
create table if not exists guides (
    slug        text primary key,                       -- canonical id, also the permalink: /g/<slug>
    app_name    text not null,
    website     text,
    source      text not null default 'generated'
                check (source in ('curated', 'generated')),
    status      text not null default 'generating'
                check (status in ('generating', 'ready', 'failed')),
    content     jsonb,                                  -- the full guide (see app/schemas.py)
    error       text,
    claimed_at  timestamptz,                            -- when a generation run started (stale-run detection)
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()      -- last successful content save (freshness)
);

-- Cost control: one row per generation, so we can cap runs per visitor and per day.
create table if not exists generation_events (
    id          bigserial primary key,
    ip_hash     text not null,                          -- salted hash, never the raw IP
    slug        text,
    created_at  timestamptz not null default now()
);
create index if not exists generation_events_ip_time on generation_events (ip_hash, created_at);
create index if not exists generation_events_time on generation_events (created_at);

-- The backend connects as the table owner (bypasses RLS). Enabling RLS with no
-- policies means the public anon key can never read or write these tables.
alter table guides enable row level security;
alter table generation_events enable row level security;
