create table public.secure_credentials_vault (
  id uuid not null default gen_random_uuid (),
  user_id uuid null,
  service_name text not null,
  key_name text not null,
  secret_id uuid null,
  created_at timestamp with time zone null default now(),
  constraint secure_credentials_vault_pkey primary key (id),
  constraint unique_user_service_key unique (user_id, service_name, key_name),
  constraint secure_credentials_vault_user_id_fkey foreign KEY (user_id) references auth.users (id)
) TABLESPACE pg_default;