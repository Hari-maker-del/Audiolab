-- Audiolab cloud metadata schema for Neon Postgres.
-- Apply only to the dedicated Audiolab Neon project.
-- Access is server-side only until an authentication provider is wired.
-- Do not expose these tables directly to anonymous browser clients.

create extension if not exists pgcrypto;

create table if not exists public.audiolab_projects (
  id uuid primary key default gen_random_uuid(),
  owner_id text not null,
  name text not null check (char_length(name) between 1 and 120),
  kind text not null default 'Audio editing',
  notes text not null default '',
  timeline jsonb not null default '{"tracks":[],"volume":1}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, owner_id)
);

create index if not exists audiolab_projects_owner_updated_idx
  on public.audiolab_projects (owner_id, updated_at desc);

create table if not exists public.audiolab_audio_assets (
  id uuid primary key default gen_random_uuid(),
  owner_id text not null,
  project_id uuid not null,
  storage_provider text not null default 'external-private-storage',
  storage_path text not null,
  file_name text not null,
  mime_type text not null default 'application/octet-stream',
  byte_size bigint not null check (byte_size > 0 and byte_size <= 104857600),
  duration_seconds double precision,
  asset_kind text not null default 'audio',
  created_at timestamptz not null default now(),
  constraint audiolab_assets_project_owner_fk
    foreign key (project_id, owner_id)
    references public.audiolab_projects (id, owner_id) on delete cascade,
  unique (storage_provider, storage_path)
);

create index if not exists audiolab_assets_owner_created_idx
  on public.audiolab_audio_assets (owner_id, created_at desc);
create index if not exists audiolab_assets_project_created_idx
  on public.audiolab_audio_assets (project_id, created_at);

create table if not exists public.audiolab_processing_jobs (
  id uuid primary key default gen_random_uuid(),
  owner_id text not null,
  project_id uuid,
  job_type text not null check (
    job_type in ('voice_generation','transcription','cleanup','stems','mastering','render')
  ),
  status text not null default 'queued' check (
    status in ('queued','running','succeeded','failed','cancelled')
  ),
  provider text not null default 'hosted-free',
  input jsonb not null default '{}'::jsonb,
  result_asset_id uuid references public.audiolab_audio_assets(id) on delete set null,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint audiolab_jobs_project_owner_fk
    foreign key (project_id, owner_id)
    references public.audiolab_projects (id, owner_id) on delete cascade
);

create index if not exists audiolab_jobs_owner_created_idx
  on public.audiolab_processing_jobs (owner_id, created_at desc);
create index if not exists audiolab_jobs_status_created_idx
  on public.audiolab_processing_jobs (status, created_at);
