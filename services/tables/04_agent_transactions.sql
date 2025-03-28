create table public.agent_transactions (
  id uuid not null default extensions.uuid_generate_v4 (),
  timestamp timestamp with time zone not null default now(),
  user_id uuid not null,
  agent_id uuid null,
  run_id uuid null,
  type text not null default 'run'::text,
  credits integer not null,
  balance bigint not null,
  description text null,
  constraint agent_transactions_pkey primary key (id),
  constraint agent_transactions_type_check check (
    (
      type = any (array['run'::text, 'refill'::text, 'other'::text])
    )
  )
) TABLESPACE pg_default;

create index IF not exists idx_agent_transactions_user_id on public.agent_transactions using btree (user_id) TABLESPACE pg_default;

create index IF not exists idx_agent_transactions_agent_id on public.agent_transactions using btree (agent_id) TABLESPACE pg_default;

create index IF not exists idx_agent_transactions_timestamp on public.agent_transactions using btree ("timestamp") TABLESPACE pg_default;

create index IF not exists idx_agent_transactions_type on public.agent_transactions using btree (type) TABLESPACE pg_default;

create index IF not exists idx_agent_transactions_user_timestamp on public.agent_transactions using btree (user_id, "timestamp" desc) TABLESPACE pg_default;