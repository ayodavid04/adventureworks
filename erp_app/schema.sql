-- The demo ERP's own tables. Kept in their own schema so the AdventureWorks schemas
-- (Microsoft's sample data) keep their structure; the app only inserts and updates rows there.
create schema if not exists erp_app;
comment on schema erp_app is 'Tables for the AdventureWorks ERP demo front end (API keys, webhooks, exports, simulator). Not Microsoft sample data.';

create table if not exists erp_app.api_keys (
    key_id      serial primary key,
    api_key     text        not null unique,   -- demo only: a real system stores a hash, not the key
    label       text        not null,
    created_at  timestamptz not null default now(),
    revoked_at  timestamptz
);

create table if not exists erp_app.webhooks (
    webhook_id  serial primary key,
    url         text        not null,
    events      text[]      not null,
    secret      text        not null,          -- used to sign every POST (HMAC-SHA256)
    active      boolean     not null default true,
    created_at  timestamptz not null default now()
);

create table if not exists erp_app.webhook_deliveries (
    delivery_id   uuid        primary key,
    webhook_id    integer     not null references erp_app.webhooks (webhook_id) on delete cascade,
    event         text        not null,
    payload       jsonb       not null,
    status        text        not null default 'pending' check (status in ('pending', 'delivered', 'failed')),
    http_status   integer,
    attempts      integer     not null default 0,
    last_error    text,
    created_at    timestamptz not null default now(),
    delivered_at  timestamptz
);

create table if not exists erp_app.export_log (
    export_id   serial primary key,
    dataset     text        not null,
    filters     jsonb       not null,
    file_format text        not null,
    row_count   integer     not null,
    created_at  timestamptz not null default now()
);

create table if not exists erp_app.simulator_state (
    id              integer     primary key default 1 check (id = 1),
    running         boolean     not null default false,
    orders_per_min  integer     not null default 6,
    started_at      timestamptz,
    stopped_at      timestamptz
);
insert into erp_app.simulator_state (id) values (1) on conflict do nothing;

-- Everything the simulator changed, so it's always clear which rows are simulated, not Microsoft's.
create table if not exists erp_app.simulator_log (
    log_id      bigserial   primary key,
    change      text        not null,   -- order.created, order.updated, customer.updated
    entity_id   integer     not null,
    detail      jsonb       not null,
    created_at  timestamptz not null default now()
);
