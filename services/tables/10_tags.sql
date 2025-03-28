create table public.tags (
  category_name text not null,
  tag_name text not null,
  parent_category text null,
  parent_name text null,
  created_at timestamp with time zone null default now(),
  constraint tags_pkey primary key (category_name, tag_name),
  constraint tags_parent_category_parent_name_fkey foreign KEY (parent_category, parent_name) references tags (category_name, tag_name)
) TABLESPACE pg_default;

create index IF not exists idx_tags_parent on public.tags using btree (parent_category, parent_name) TABLESPACE pg_default;

create index IF not exists idx_tags_name_gin on public.tags using gin (tag_name gin_trgm_ops) TABLESPACE pg_default;

create index IF not exists idx_tags_category_gin on public.tags using gin (category_name gin_trgm_ops) TABLESPACE pg_default;