create table public.prompts (
  id uuid not null default gen_random_uuid (),
  created_at timestamp with time zone not null default now(),
  prompt_text text null,
  version smallint null default '1'::smallint,
  name text null,
  is_active boolean null default false,
  constraint prompts_pkey primary key (id)
) TABLESPACE pg_default;