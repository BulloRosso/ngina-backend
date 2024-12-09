-- Enable necessary extensions
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- Profiles table
create table profiles (
    id uuid primary key default uuid_generate_v4(),
    first_name text not null,
    last_name text not null,
    date_of_birth date not null,
    place_of_birth text not null,
    gender text not null,
    children text[] default '{}',
    spoken_languages text[] default '{}',
    profile_image_url text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Interview sessions table
create table interview_sessions (
    id uuid primary key default uuid_generate_v4(),
    profile_id uuid references profiles(id) on delete cascade not null,
    category text not null,
    started_at timestamptz default now(),
    completed_at timestamptz,
    summary text,
    emotional_state jsonb,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Memories table
create table memories (
    id uuid primary key default uuid_generate_v4(),
    profile_id uuid references profiles(id) on delete cascade not null,
    session_id uuid references interview_sessions(id) on delete cascade not null,
    category text not null,
    description text not null,
    time_period date not null,
    location jsonb,
    emotions text[] default '{}',
    people jsonb[] default '{}',
    image_urls text[] default '{}',
    audio_url text,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    sentiment_analysis jsonb
);

-- Memory sentiments table
create table memory_sentiments (
    id uuid primary key default uuid_generate_v4(),
    memory_id uuid references memories(id) on delete cascade not null,
    sentiment_data jsonb not null,
    emotional_triggers text[] default '{}',
    intensity float default 0.0,
    requires_support boolean default false,
    created_at timestamptz default now()
);

-- Achievements table
create table achievements (
    id text primary key,
    type text not null,
    titles jsonb not null, -- Multilingual titles
    descriptions jsonb not null, -- Multilingual descriptions
    icon text not null,
    color text not null,
    required_count integer not null,
    bonus_achievement_id text references achievements(id),
    created_at timestamptz default now()
);

-- Achievement progress table
create table achievement_progress (
    id uuid primary key default uuid_generate_v4(),
    profile_id uuid references profiles(id) on delete cascade not null,
    achievement_id text references achievements(id) on delete cascade not null,
    current_count integer default 0,
    completed boolean default false,
    unlocked_at timestamptz,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique(profile_id, achievement_id)
);

-- PDF exports table
create table pdf_exports (
    id uuid primary key default uuid_generate_v4(),
    profile_id uuid references profiles(id) on delete cascade not null,
    file_url text not null,
    generated_at timestamptz default now(),
    category text,
    date_range tstzrange,
    created_at timestamptz default now()
);

-- Triggers for updated_at timestamps
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger profiles_updated_at
    before update on profiles
    for each row
    execute function update_updated_at();

create trigger sessions_updated_at
    before update on interview_sessions
    for each row
    execute function update_updated_at();

create trigger memories_updated_at
    before update on memories
    for each row
    execute function update_updated_at();

create trigger achievement_progress_updated_at
    before update on achievement_progress
    for each row
    execute function update_updated_at();

-- Insert default achievements
insert into achievements (id, type, titles, descriptions, icon, color, required_count) values
    ('first_memories', 'memory_milestones', 
     '{"en": "Memory Keeper", "de": "Erinnerungsbewahrer"}',
     '{"en": "Shared your first 5 memories", "de": "Ihre ersten 5 Erinnerungen geteilt"}',
     'AutoStories', '#4CAF50', 5),

    ('photo_collector', 'media_sharing',
     '{"en": "Photo Collector", "de": "Fotograf"}',
     '{"en": "Added photos to 10 memories", "de": "10 Erinnerungen mit Fotos ergänzt"}',
     'PhotoLibrary', '#2196F3', 10),

    ('childhood_expert', 'category_completion',
     '{"en": "Childhood Chronicles", "de": "Kindheitserinnerungen"}',
     '{"en": "Shared 8 childhood memories", "de": "8 Kindheitserinnerungen geteilt"}',
     'ChildCare', '#9C27B0', 8),

    ('family_historian', 'family_connection',
     '{"en": "Family Historian", "de": "Familienchronist"}',
     '{"en": "Mentioned 10 different family members", "de": "10 verschiedene Familienmitglieder erwähnt"}',
     'People', '#FF9800', 10),

    ('consistent_sharing', 'session_streaks',
     '{"en": "Regular Storyteller", "de": "Regelmäßiger Erzähler"}',
     '{"en": "Completed 5 interview sessions", "de": "5 Interviewsitzungen abgeschlossen"}',
     'Timer', '#FF5722', 5),

    ('emotional_journey', 'emotional_sharing',
     '{"en": "Heart of Gold", "de": "Herz aus Gold"}',
     '{"en": "Shared deeply emotional memories", "de": "Emotional bedeutsame Erinnerungen geteilt"}',
     'Favorite', '#E91E63', 3);

-- RLS Policies
alter table profiles enable row level security;
alter table interview_sessions enable row level security;
alter table memories enable row level security;
alter table memory_sentiments enable row level security;
alter table achievement_progress enable row level security;
alter table pdf_exports enable row level security;

-- Create indexes for better performance
create index idx_memories_profile_id on memories(profile_id);
create index idx_memories_session_id on memories(session_id);
create index idx_memories_time_period on memories(time_period);
create index idx_sessions_profile_id on interview_sessions(profile_id);
create index idx_achievement_progress_profile on achievement_progress(profile_id);
create index idx_memory_sentiments_memory on memory_sentiments(memory_id);

-- Create view for achievement statistics
create view achievement_statistics as
select 
    p.id as profile_id,
    p.first_name,
    p.last_name,
    count(distinct ap.achievement_id) as completed_achievements,
    count(distinct m.id) as total_memories,
    count(distinct m.id) filter (where m.image_urls != '{}') as memories_with_photos,
    count(distinct m.session_id) as total_sessions
from profiles p
left join achievement_progress ap on p.id = ap.profile_id and ap.completed = true
left join memories m on p.id = m.profile_id
group by p.id, p.first_name, p.last_name;

-- Storage configuration (run this after creating the bucket in Supabase dashboard)
insert into storage.buckets (id, name) values ('profile-images', 'Profile Images') on conflict do nothing;
insert into storage.buckets (id, name) values ('memory-media', 'Memory Media') on conflict do nothing;
insert into storage.buckets (id, name) values ('exports', 'PDF Exports') on conflict do nothing;