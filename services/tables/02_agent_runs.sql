create table public.agent_runs (
  id uuid not null default extensions.uuid_generate_v4 (),
  created_at timestamp with time zone not null default now(),
  user_id uuid null,
  results jsonb null,
  status text null default 'pending'::text,
  sum_credits integer null default 0,
  workflow_id text null,
  finished_at timestamp with time zone null,
  agent_id uuid null,
  sub_agents jsonb null,
  email_settings jsonb null,
  prompt text null,
  execution_id text null,
  constraint agent_runs_pkey primary key (id)
) TABLESPACE pg_default;

create index IF not exists idx_agent_runs_user_created_agent on public.agent_runs using btree (user_id, created_at desc, agent_id) TABLESPACE pg_default;