-- Same two tables as schema.sql, for the optional local SQLite mode (no Supabase needed).
create table if not exists guides (
    slug        text primary key,
    app_name    text not null,
    website     text,
    source      text not null default 'generated' check (source in ('curated', 'generated')),
    status      text not null default 'generating' check (status in ('generating', 'ready', 'failed')),
    content     text,                       -- the full guide as JSON text
    error       text,
    claimed_at  text,                       -- ISO-8601 UTC
    created_at  text not null,
    updated_at  text not null
);

create table if not exists generation_events (
    id          integer primary key autoincrement,
    ip_hash     text not null,
    slug        text,
    created_at  text not null
);
create index if not exists generation_events_ip_time on generation_events (ip_hash, created_at);
