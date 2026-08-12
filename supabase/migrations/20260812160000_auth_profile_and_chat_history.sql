-- Durable homes for the two things the browser used to own alone:
-- the working FinancialProfile and the chat transcript.
--
-- The profile is stored as jsonb rather than as ~20 typed columns on purpose.
-- ARCHITECTURE.md makes the pydantic model in
-- services/api/app/domain/financial_profile.py the single canonical schema, and
-- a hand-maintained SQL mirror would be a second one to keep in sync -- drifting
-- the first time a field is added. Postgres stores the contract; it does not
-- redefine it.

create table if not exists public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  profile jsonb not null,
  -- Extracted, not passed in: a generated column cannot drift from the document
  -- it describes, which is the whole point of carrying schemaVersion at all.
  schema_version integer generated always as (((profile ->> 'schemaVersion'))::integer) stored,
  updated_at timestamptz not null default now(),

  -- Cheap structural gate so a malformed write fails here rather than deep
  -- inside a chart. The full shape is still validated by pydantic and by
  -- isFinancialProfile() in apps/web/lib/storage.ts.
  constraint profiles_profile_is_object check (jsonb_typeof(profile) = 'object'),
  constraint profiles_schema_version_present check ((profile ->> 'schemaVersion') is not null)
);

create table if not exists public.chat_messages (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null,
  content text not null,
  created_at timestamptz not null default now(),

  constraint chat_messages_role_valid check (role in ('user', 'assistant'))
);

-- Transcripts are always read as "this user's messages, in order". The identity
-- column supplies the ordering, so created_at never has to break a tie between
-- two messages written inside the same millisecond.
create index if not exists chat_messages_user_id_id_idx
  on public.chat_messages (user_id, id);

-- A financial profile is about as sensitive as this product gets, so both
-- tables are owner-only with no public read path whatsoever.
alter table public.profiles enable row level security;
alter table public.chat_messages enable row level security;

drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own on public.profiles
  for select using ((select auth.uid()) = user_id);

drop policy if exists profiles_insert_own on public.profiles;
create policy profiles_insert_own on public.profiles
  for insert with check ((select auth.uid()) = user_id);

drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own on public.profiles
  for update using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists profiles_delete_own on public.profiles;
create policy profiles_delete_own on public.profiles
  for delete using ((select auth.uid()) = user_id);

drop policy if exists chat_messages_select_own on public.chat_messages;
create policy chat_messages_select_own on public.chat_messages
  for select using ((select auth.uid()) = user_id);

drop policy if exists chat_messages_insert_own on public.chat_messages;
create policy chat_messages_insert_own on public.chat_messages
  for insert with check ((select auth.uid()) = user_id);

drop policy if exists chat_messages_delete_own on public.chat_messages;
create policy chat_messages_delete_own on public.chat_messages
  for delete using ((select auth.uid()) = user_id);

-- updated_at is maintained here rather than by the caller so that a client that
-- forgets to send it cannot silently freeze the timestamp.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();
