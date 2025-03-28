create table public.scratchpad_files (
  id uuid not null default gen_random_uuid (),
  user_id uuid not null,
  run_id uuid not null,
  agent_id uuid not null,
  filename text not null,
  path text not null,
  metadata jsonb not null,
  created_at timestamp with time zone null default now(),
  constraint scratchpad_files_pkey primary key (id),
  constraint scratchpad_files_user_id_run_id_agent_id_filename_key unique (user_id, run_id, agent_id, filename),
  constraint scratchpad_files_user_id_fkey foreign KEY (user_id) references auth.users (id)
) TABLESPACE pg_default;