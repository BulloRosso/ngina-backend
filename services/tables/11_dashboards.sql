create table public.dashboards (
  id uuid not null default gen_random_uuid (),
  created_at timestamp with time zone not null default now(),
  configuration jsonb null,
  agents jsonb null,
  is_anonymous boolean null default true,
  user_id uuid null default gen_random_uuid (),
  description jsonb null default '{"en": {"title": "Dashboard", "description": "All you have to know about your automations!"}}'::jsonb,
  style jsonb null default '{"layout": {"logoUrl": "https://abc.com", "templateName": "default"}, "components": []}'::jsonb,
  constraint dashboards_pkey primary key (id)
) TABLESPACE pg_default;