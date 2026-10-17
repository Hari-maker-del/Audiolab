-- Audiolab cloud foundation. Apply only to a dedicated Audiolab Supabase project.
-- No service-role keys are used by the browser.
create extension if not exists pgcrypto;

create table if not exists public.audiolab_projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 120),
  kind text not null default 'Audio editing',
  notes text not null default '',
  timeline jsonb not null default '{"tracks":[],"volume":1}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, owner_id)
);
create index if not exists audiolab_projects_owner_updated_idx
  on public.audiolab_projects(owner_id, updated_at desc);

create table if not exists public.audiolab_audio_assets (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.audiolab_projects(id) on delete cascade,
  storage_path text not null unique,
  file_name text not null,
  mime_type text not null default 'application/octet-stream',
  byte_size bigint not null check (byte_size > 0 and byte_size <= 104857600),
  duration_seconds double precision,
  asset_kind text not null default 'audio',
  created_at timestamptz not null default now(),
  constraint audiolab_assets_project_owner_fk
    foreign key (project_id, owner_id)
    references public.audiolab_projects(id, owner_id)
    on delete cascade
);
-- Composite unique key enables the ownership-enforcing composite foreign key.
create index if not exists audiolab_assets_owner_created_idx
  on public.audiolab_audio_assets(owner_id, created_at desc);
create index if not exists audiolab_assets_project_created_idx
  on public.audiolab_audio_assets(project_id, created_at);

create table if not exists public.audiolab_processing_jobs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid references public.audiolab_projects(id) on delete set null,
  job_type text not null check (job_type in ('voice_generation','transcription','cleanup','stems','mastering','render')),
  status text not null default 'queued' check (status in ('queued','running','succeeded','failed','cancelled')),
  provider text not null default 'hosted-free',
  input jsonb not null default '{}'::jsonb,
  result_asset_id uuid references public.audiolab_audio_assets(id) on delete set null,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists audiolab_jobs_owner_created_idx
  on public.audiolab_processing_jobs(owner_id, created_at desc);

grant select, insert, update, delete on public.audiolab_projects to authenticated;
grant select, insert, delete on public.audiolab_audio_assets to authenticated;
grant select, insert on public.audiolab_processing_jobs to authenticated;

alter table public.audiolab_projects enable row level security;
alter table public.audiolab_audio_assets enable row level security;
alter table public.audiolab_processing_jobs enable row level security;

drop policy if exists "Users read own Audiolab projects" on public.audiolab_projects;
create policy "Users read own Audiolab projects" on public.audiolab_projects
  for select to authenticated using ((select auth.uid()) = owner_id);
drop policy if exists "Users create own Audiolab projects" on public.audiolab_projects;
create policy "Users create own Audiolab projects" on public.audiolab_projects
  for insert to authenticated with check ((select auth.uid()) = owner_id);
drop policy if exists "Users update own Audiolab projects" on public.audiolab_projects;
create policy "Users update own Audiolab projects" on public.audiolab_projects
  for update to authenticated using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);
drop policy if exists "Users delete own Audiolab projects" on public.audiolab_projects;
create policy "Users delete own Audiolab projects" on public.audiolab_projects
  for delete to authenticated using ((select auth.uid()) = owner_id);

drop policy if exists "Users read own Audiolab assets" on public.audiolab_audio_assets;
create policy "Users read own Audiolab assets" on public.audiolab_audio_assets
  for select to authenticated using ((select auth.uid()) = owner_id);
drop policy if exists "Users create own Audiolab assets" on public.audiolab_audio_assets;
create policy "Users create own Audiolab assets" on public.audiolab_audio_assets
  for insert to authenticated with check (
    (select auth.uid()) = owner_id and exists (
      select 1 from public.audiolab_projects p
      where p.id = project_id and p.owner_id = (select auth.uid())
    )
  );
drop policy if exists "Users delete own Audiolab assets" on public.audiolab_audio_assets;
create policy "Users delete own Audiolab assets" on public.audiolab_audio_assets
  for delete to authenticated using ((select auth.uid()) = owner_id);

drop policy if exists "Users read own Audiolab jobs" on public.audiolab_processing_jobs;
create policy "Users read own Audiolab jobs" on public.audiolab_processing_jobs
  for select to authenticated using ((select auth.uid()) = owner_id);
drop policy if exists "Users enqueue own Audiolab jobs" on public.audiolab_processing_jobs;
create policy "Users enqueue own Audiolab jobs" on public.audiolab_processing_jobs
  for insert to authenticated with check (
    (select auth.uid()) = owner_id and
    (project_id is null or exists (
      select 1 from public.audiolab_projects p
      where p.id = project_id and p.owner_id = (select auth.uid())
    ))
  );

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('audiolab-audio', 'audiolab-audio', false, 104857600,
  array['audio/wav','audio/mpeg','audio/mp4','audio/aac','audio/ogg','audio/webm','audio/flac','audio/x-flac','audio/aiff','audio/x-aiff','application/octet-stream'])
on conflict (id) do update set public = false, file_size_limit = 104857600;

drop policy if exists "Users read own Audiolab audio objects" on storage.objects;
create policy "Users read own Audiolab audio objects" on storage.objects
  for select to authenticated using (
    bucket_id = 'audiolab-audio' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
drop policy if exists "Users upload own Audiolab audio objects" on storage.objects;
create policy "Users upload own Audiolab audio objects" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'audiolab-audio' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
drop policy if exists "Users update own Audiolab audio objects" on storage.objects;
create policy "Users update own Audiolab audio objects" on storage.objects
  for update to authenticated using (
    bucket_id = 'audiolab-audio' and (storage.foldername(name))[1] = (select auth.uid())::text
  ) with check (
    bucket_id = 'audiolab-audio' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
drop policy if exists "Users delete own Audiolab audio objects" on storage.objects;
create policy "Users delete own Audiolab audio objects" on storage.objects
  for delete to authenticated using (
    bucket_id = 'audiolab-audio' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
