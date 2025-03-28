create table public.human_in_the_loop (
  id uuid not null default gen_random_uuid (),
  created_at timestamp with time zone not null default now(),
  run_id uuid null,
  email_settings jsonb null,
  status text null default 'pending'::text,
  workflow_id text null,
  reason text null,
  callback_url text null,
  constraint human_in_the_loop_pkey primary key (id)
) TABLESPACE pg_default;