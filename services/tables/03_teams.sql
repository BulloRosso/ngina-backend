create table public.teams (
  id uuid not null default gen_random_uuid (),
  created_at timestamp with time zone not null default now(),
  owner_id text null,
  agents jsonb null,
  constraint teams_pkey primary key (id)
) TABLESPACE pg_default;