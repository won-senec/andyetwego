-- ============================================================
--  Likes backend for the blog (run ONCE in Supabase)
--  Dashboard -> SQL Editor -> paste this -> Run
-- ============================================================

-- 1. Table: one row per post, holding its total like count.
create table if not exists public.likes (
    post_id text primary key,
    count   integer not null default 0
);

-- 2. Lock the table down with Row Level Security.
--    Visitors may READ counts, but can only CHANGE them through
--    the controlled function below (never write the table directly).
alter table public.likes enable row level security;

drop policy if exists "Public can read likes" on public.likes;
create policy "Public can read likes"
    on public.likes
    for select
    to anon
    using (true);

-- 3. Atomic +/-1 function. Clamps delta so a visitor can only ever
--    move a count by exactly one, and never below zero. Creates the
--    row automatically the first time a post is liked.
create or replace function public.bump_likes(pid text, delta int)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    d         integer;
    new_count integer;
begin
    -- force delta to be exactly +1 or -1, ignoring whatever was sent
    if delta > 0 then d := 1; else d := -1; end if;

    insert into public.likes (post_id, count)
    values (pid, greatest(0, d))
    on conflict (post_id)
    do update set count = greatest(0, public.likes.count + d)
    returning count into new_count;

    return new_count;
end;
$$;

-- 4. Let anonymous visitors call the function (but nothing else).
grant execute on function public.bump_likes(text, int) to anon;

-- 5. No seed data: every post starts at 0 and creates its own row on the
--    first like. (Display counts in the HTML are all 0 to match.)
